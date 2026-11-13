"""Minimal OpenAI-compatible transport; no credentials enter persisted artifacts."""

import asyncio
import hashlib
import json
import math
import time
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from agentprobe.models import Message, Reply, Tool, ToolCall


class ProviderError(RuntimeError):
    """Safe, deliberately body-free provider failure."""


def json_object(text: str) -> dict:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Model JSON contains duplicate keys")
            value[key] = item
        return value

    def invalid_constant(value):
        raise ValueError("Model JSON contains a non-finite number")

    data = json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)
    if not isinstance(data, dict):
        raise ValueError("Model JSON must be an object")
    return data


class Provider(Protocol):
    name: str

    async def chat(
        self, messages: list[Message], *, json_mode: bool = False, tools: list[Tool] = ()
    ) -> Reply: ...


def wire_message(message: Message) -> dict:
    data = {"role": message.role, "content": message.content}
    if message.tool_calls:
        data["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in message.tool_calls
        ]
    return data


class OpenAIProvider:
    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        key: str,
        model: str,
        *,
        retries: int = 0,
        input_price: float | None = None,
        output_price: float | None = None,
    ):
        if type(retries) is not int or not 0 <= retries <= 5:
            raise ValueError("retries must be 0..5")
        if (input_price is None) != (output_price is None) or any(
            not math.isfinite(price) or price < 0
            for price in (input_price, output_price)
            if price is not None
        ):
            raise ValueError("Supply both finite nonnegative per-million token prices")
        self.retries = retries
        self.input_price = input_price
        self.output_price = output_price
        self.requests = self.attempts = self.failures = 0
        self.prompt_tokens = self.completion_tokens = self.unknown_usage_requests = 0
        self.duration_seconds = 0.0
        url = urlsplit(base_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("Provider URL must be HTTP(S), without credentials, query or fragment")
        if not model.strip():
            raise ValueError("Provider model must not be empty")
        self.client = client
        self.endpoint = base_url.rstrip("/")
        if not self.endpoint.endswith("/chat/completions"):
            self.endpoint += "/chat/completions"
        self.key = key
        self.model = model
        endpoint_id = hashlib.sha256(self.endpoint.encode()).hexdigest()[:12]
        self.name = f"openai-compatible:{model}@{endpoint_id}"

    def accounting(self) -> dict:
        cost = None
        if self.input_price is not None and not self.unknown_usage_requests:
            cost = (
                self.prompt_tokens * self.input_price + self.completion_tokens * self.output_price
            ) / 1_000_000
        return {
            "provider": self.name,
            "requests": self.requests,
            "attempts": self.attempts,
            "failures": self.failures,
            "duration_seconds": self.duration_seconds,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "unknown_usage_requests": self.unknown_usage_requests,
            "input_price_per_million": self.input_price,
            "output_price_per_million": self.output_price,
            "estimated_cost_usd": cost,
        }

    async def _request(self, body: dict, headers: dict) -> httpx.Response:
        for attempt in range(self.retries + 1):
            self.attempts += 1
            delay = min(0.5 * 2**attempt, 8)
            try:
                response = await self.client.post(self.endpoint, json=body, headers=headers)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if (
                    exc.response.status_code not in {429, 500, 502, 503, 504}
                    or attempt == self.retries
                ):
                    raise ProviderError(
                        f"Chat endpoint returned HTTP {exc.response.status_code}"
                    ) from None
                try:
                    retry_after = float(exc.response.headers.get("Retry-After", ""))
                    if math.isfinite(retry_after) and retry_after >= 0:
                        delay = min(retry_after, 30)
                except ValueError:
                    pass
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if attempt == self.retries:
                    raise ProviderError("Chat endpoint transport failure") from None
            except httpx.HTTPError:
                raise ProviderError("Chat endpoint transport failure") from None
            await asyncio.sleep(delay)
        raise AssertionError("Unreachable retry state")

    async def chat(
        self, messages: list[Message], *, json_mode: bool = False, tools: list[Tool] = ()
    ) -> Reply:
        began = time.perf_counter()
        self.requests += 1
        try:
            return await self._chat(messages, json_mode=json_mode, tools=tools)
        except BaseException:
            self.failures += 1
            raise
        finally:
            self.duration_seconds += time.perf_counter() - began

    async def _chat(self, messages: list[Message], *, json_mode: bool, tools: list[Tool]) -> Reply:
        body = {
            "model": self.model,
            "messages": [wire_message(message) for message in messages],
            "temperature": 0,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if tools:
            body["tools"] = [{"type": "function", "function": tool.model_dump()} for tool in tools]
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        self.unknown_usage_requests += 1
        response = await self._request(body, headers)
        try:
            usage = response.json().get("usage")
            if isinstance(usage, dict):
                prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
                if all(type(value) is int and value >= 0 for value in (prompt, completion)):
                    self.prompt_tokens += prompt
                    self.completion_tokens += completion
                    self.unknown_usage_requests -= 1
        except (ValueError, AttributeError):
            pass
        try:
            choice = response.json()["choices"][0]
            if choice.get("finish_reason") not in {"stop", "tool_calls"}:
                raise ValueError("Incomplete completion")
            message = choice["message"]
            if message.get("role") != "assistant":
                raise ValueError("Expected assistant reply")
            calls = [
                ToolCall(
                    id=call["id"],
                    name=call["function"]["name"],
                    arguments=json_object(call["function"]["arguments"]),
                )
                for call in message.get("tool_calls", [])
            ]
            return Reply(content=message.get("content") or "", tool_calls=calls)
        except (KeyError, IndexError, AttributeError, TypeError, ValueError, ValidationError):
            raise ProviderError(
                "Chat endpoint returned an invalid or incomplete completion"
            ) from None
