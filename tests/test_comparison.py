import pytest

from agentprobe.adapters import CallableAgent
from agentprobe.comparison import compare
from agentprobe.demo_agents import broken_agent, demo_spec, good_agent
from agentprobe.judge import Judge
from agentprobe.mock import MockProvider
from agentprobe.runner import run_suite
from agentprobe.scenarios import generate_suite


async def runs():
    spec = demo_spec()
    suite = await generate_suite(spec, MockProvider(), per_persona=4, seed=42)
    judge = Judge(MockProvider())
    return [
        await run_suite(spec, suite, CallableAgent(fn, name), judge, concurrency=4, timeout=2)
        for fn, name in [(good_agent, "good"), (broken_agent, "broken")]
    ]


@pytest.mark.asyncio
async def test_comparison_reports_paired_regressions():
    good, broken = await runs()
    result = compare(good, broken, samples=2000, seed=42)
    assert result.n == 24
    assert result.metrics["overall"].baseline == 1
    assert result.metrics["overall"].candidate == pytest.approx(1 / 6)
    assert result.metrics["overall"].interval.regressed
    assert result.metrics["tone"].interval.ci_high < 0
    assert result.metrics["tool_misuse"].interval.regressed
    assert compare(good, good, samples=100, seed=42).regressions == []


@pytest.mark.parametrize("mutation", ["suite", "judge", "error"])
@pytest.mark.asyncio
async def test_invalid_comparisons_fail_closed(mutation):
    good, broken = await runs()
    if mutation == "suite":
        broken.suite.seed += 1
    elif mutation == "judge":
        broken.judge = "different-judge"
    else:
        broken.conversations[0].grades = None
        broken.conversations[0].error = "timeout"
    with pytest.raises(ValueError):
        compare(good, broken, samples=100, seed=1)
