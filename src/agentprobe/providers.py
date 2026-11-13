"""Minimal OpenAI-compatible transport; no credentials enter persisted artifacts."""

import hashlib
import json
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
    def __init__(self, client: httpx.AsyncClient, base_url: str, key: str, model: str):
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

    async def chat(
        self, messages: list[Message], *, json_mode: bool = False, tools: list[Tool] = ()
    ) -> Reply:
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
        try:
            response = await self.client.post(self.endpoint, json=body, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"Chat endpoint returned HTTP {exc.response.status_code}") from None
        except httpx.HTTPError:
            raise ProviderError("Chat endpoint transport failure") from None
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
