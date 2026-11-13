import pytest_asyncio

from agentprobe.adapters import CallableAgent
from agentprobe.demo_agents import broken_agent, demo_spec
from agentprobe.judge import Judge
from agentprobe.mock import MockProvider
from agentprobe.runner import run_suite
from agentprobe.scenarios import generate_suite


@pytest_asyncio.fixture
async def completed_run():
    spec = demo_spec()
    suite = await generate_suite(spec, MockProvider(), per_persona=1, seed=42)
    return await run_suite(spec, suite, CallableAgent(broken_agent, "broken"), Judge(MockProvider()), concurrency=3, timeout=2)
