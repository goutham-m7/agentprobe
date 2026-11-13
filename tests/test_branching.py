import pytest
from pydantic import ValidationError

from agentprobe.adapters import CallableAgent
from agentprobe.comparison import compare
from agentprobe.demo_agents import demo_spec
from agentprobe.judge import Judge
from agentprobe.mock import MockProvider
from agentprobe.models import Scenario, Suite
from agentprobe.runner import run_suite


def scenario(branches):
    return Scenario(
        id="branch",
        persona="confused",
        objective="Help",
        turns=["Start", "Default", "Refusal followup"],
        branches=branches,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply,expected",
    [
        ("I CANNOT disclose", ["Start", "Refusal followup"]),
        ("Here you go", ["Start", "Default", "Refusal followup"]),
    ],
)
async def test_branch_uses_latest_reply_case_insensitively(reply, expected):
    plan = scenario([{"after_turn": 1, "contains": "cannot", "next_turn": 3}])
    suite = Suite(spec_fingerprint=demo_spec().fingerprint, seed=1, scenarios=[plan])
    result = await run_suite(
        demo_spec(),
        suite,
        CallableAgent(lambda _: reply, "target"),
        Judge(MockProvider()),
        concurrency=1,
        timeout=2,
    )
    assert result.conversations[0].error is None
    assert [m.content for m in result.conversations[0].messages if m.role == "user"] == expected


@pytest.mark.parametrize(
    "branch",
    [
        {"after_turn": 1, "contains": "x", "next_turn": 1},
        {"after_turn": 1, "contains": "x", "next_turn": 4},
        {"after_turn": 0, "contains": "x", "next_turn": 2},
        {"after_turn": 1, "contains": " ", "next_turn": 2},
    ],
)
def test_invalid_branches_fail_before_execution(branch):
    with pytest.raises(ValidationError):
        scenario([branch])


def test_first_matching_branch_wins_and_fixed_plans_still_load():
    plan = scenario(
        [
            {"after_turn": 1, "contains": "no", "next_turn": 2},
            {"after_turn": 1, "contains": "no", "next_turn": 3},
        ]
    )
    assert plan.following_turn(1, "NO") == 2
    assert plan.following_turn(2, "NO") == 3
    assert Scenario(id="old", persona="angry", objective="Help", turns=["Hi"]).branches == []


@pytest.mark.asyncio
async def test_branch_comparison_warns_that_realized_prompts_can_differ():
    first = scenario([{"after_turn": 1, "contains": "cannot", "next_turn": 3}])
    second = first.model_copy(update={"id": "second"})
    suite = Suite(spec_fingerprint=demo_spec().fingerprint, seed=1, scenarios=[first, second])
    runs = [
        await run_suite(
            demo_spec(),
            suite,
            CallableAgent(lambda _, reply=reply: reply, "target"),
            Judge(MockProvider()),
            concurrency=1,
            timeout=2,
        )
        for reply in ["cannot", "okay"]
    ]
    result = compare(*runs, samples=100, seed=1)
    assert any("realized user prompts may differ" in warning for warning in result.warnings)
