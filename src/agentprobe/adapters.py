"""Target adapters. Python targets are trusted local code, not a sandbox."""

import asyncio
import importlib
import inspect
from collections.abc import Callable
from typing import Protocol

from agentprobe.models import Message, Reply, Tool
from agentprobe.providers import Provider


class Agent(Protocol):
    name: str

    async def respond(self, messages: list[Message], tools: list[Tool]) -> Reply: ...


class HttpAgent:
    def __init__(self, provider: Provider):
        self.provider = provider
        self.name = provider.name

    async def respond(self, messages: list[Message], tools: list[Tool]) -> Reply:
        return await self.provider.chat(messages, tools=tools)


class CallableAgent:
    def __init__(self, function: Callable, name: str):
        self.function = function
        self.name = name

    async def respond(self, messages: list[Message], tools: list[Tool]) -> Reply:
        # Offload sync code: a blocking SDK must not block every conversation.
        if inspect.iscoroutinefunction(self.function):
            result = await self.function(messages)
        else:
            result = await asyncio.to_thread(self.function, messages)
            if inspect.isawaitable(result):
                result = await result
        if isinstance(result, str):
            return Reply(content=result)
        if isinstance(result, Reply):
            return result
        raise ValueError("Python callable must return a string or Reply")


def load_callable(target: str) -> CallableAgent:
    try:
        module, attribute = target.split(":", 1)
        function = getattr(importlib.import_module(module), attribute)
        if not callable(function):
            raise ValueError("Not callable")
    except (ValueError, ImportError, AttributeError) as exc:
        raise ValueError("Expected an importable Python callable as module:function") from exc
    return CallableAgent(function, target)
