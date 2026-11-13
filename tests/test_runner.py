import asyncio
import json

import pytest

from agentprobe.adapters import CallableAgent
from agentprobe.demo_agents import demo_spec
from agentprobe.judge import Judge
from agentprobe.models import CRITERIA, Message, Reply, Scenario, Suite, ToolCall
from agentprobe.runner import run_suite


class PassingProvider:
    name = "test-judge"

    async def chat(self, messages, **kwargs):
        request = json.loads(messages[-1].content)
        quote = next(
            message["content"]
            for message in reversed(request["messages"])
            if message["role"] == "assistant" and message["content"]
        )
        return Reply(
            content=json.dumps(
                {
                    "scores": {
                        key: {"passed": True, "reason": "Supported", "evidence": quote}
                        for key in CRITERIA
                    }
                }
            )
        )


def suite(count=4):
    return Suite(
        spec_fingerprint=demo_spec().fingerprint,
        seed=1,
        scenarios=[
            Scenario(
                id=f"s{n}", persona="confused", objective="Help", turns=["First", "Second", "Third"]
            )
            for n in range(count)
        ],
    )


@pytest.mark.asyncio
async def test_runner_bounds_concurrency_and_preserves_full_history():
    active = peak = 0
    histories = []

    async def target(messages):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        histories.append([m.role for m in messages])
        await asyncio.sleep(0.005)
        active -= 1
        return "Helpful answer"

    result = await run_suite(
        demo_spec(),
        suite(),
        CallableAgent(target, "target"),
        Judge(PassingProvider()),
        concurrency=2,
        timeout=2,
    )
    assert peak == 2
    assert len(result.conversations) == 4
    assert all(len(c.messages) == 7 and c.error is None for c in result.conversations)
    assert ["system", "user", "assistant", "user", "assistant", "user"] in histories
    assert [c.scenario_id for c in result.conversations] == ["s0", "s1", "s2", "s3"]


@pytest.mark.asyncio
async def test_runner_timeout_is_not_a_rubric_failure():
    async def target(messages):
        await asyncio.sleep(1)
        return "late"

    result = await run_suite(
        demo_spec(),
        suite(1),
        CallableAgent(target, "slow"),
        Judge(PassingProvider()),
        concurrency=1,
        timeout=0.01,
    )
    assert result.conversations[0].grades is None
    assert result.conversations[0].error == "Conversation timed out"


@pytest.mark.asyncio
async def test_exceptions_are_safe_and_isolated():
    def broken(messages):
        raise RuntimeError("API_KEY=should-not-persist")

    result = await run_suite(
        demo_spec(),
        suite(2),
        CallableAgent(broken, "broken"),
        Judge(PassingProvider()),
        concurrency=2,
        timeout=1,
    )
    assert all(c.error == "Agent or judge failed (RuntimeError)" for c in result.conversations)
    assert "should-not-persist" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_tool_attempts_stop_before_fabricated_tool_results():
    def tool_agent(messages):
        return Reply(
            content="Looking up",
            tool_calls=[ToolCall(id="t1", name="lookup_order", arguments={"order_number": "123"})],
        )

    result = await run_suite(
        demo_spec(),
        suite(1),
        CallableAgent(tool_agent, "tools"),
        Judge(PassingProvider()),
        concurrency=1,
        timeout=1,
    )
    assert len(result.conversations[0].messages) == 3
    assert result.conversations[0].messages[-1].tool_calls[0].name == "lookup_order"


@pytest.mark.parametrize("concurrency,timeout", [(0, 1), (1, 0), (-1, 1)])
@pytest.mark.asyncio
async def test_invalid_execution_limits(concurrency, timeout):
    with pytest.raises(ValueError):
        await run_suite(
            demo_spec(),
            suite(1),
            CallableAgent(lambda _: "ok", "t"),
            Judge(PassingProvider()),
            concurrency=concurrency,
            timeout=timeout,
        )


@pytest.mark.asyncio
async def test_wrong_spec_is_rejected_before_target_calls():
    different = demo_spec().model_copy(update={"name": "different"})
    with pytest.raises(ValueError, match="fingerprint"):
        await run_suite(
            different,
            suite(1),
            CallableAgent(lambda _: "ok", "t"),
            Judge(PassingProvider()),
            concurrency=1,
            timeout=1,
        )


@pytest.mark.parametrize("bad", ["not json", '{"scores": {}}'])
@pytest.mark.asyncio
async def test_judge_rejects_invalid_schema(bad):
    class Invalid:
        name = "invalid"

        async def chat(self, messages, **kwargs):
            return Reply(content=bad)

    with pytest.raises(ValueError):
        await Judge(Invalid()).score(
            demo_spec(), [Message(role="assistant", content="hello")], "Help"
        )


@pytest.mark.asyncio
async def test_judge_rejects_fabricated_evidence():
    class Fabricator:
        name = "fabricator"

        async def chat(self, messages, **kwargs):
            return Reply(
                content=json.dumps(
                    {
                        "scores": {
                            key: {"passed": True, "reason": "x", "evidence": "invented quote"}
                            for key in CRITERIA
                        }
                    }
                )
            )

    with pytest.raises(ValueError, match="evidence"):
        await Judge(Fabricator()).score(
            demo_spec(), [Message(role="assistant", content="hello")], "Help"
        )
