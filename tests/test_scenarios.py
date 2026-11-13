import json

import pytest

from agentprobe.demo_agents import demo_spec
from agentprobe.models import PERSONAS, Reply
from agentprobe.mock import MockProvider
from agentprobe.scenarios import generate_suite


@pytest.mark.asyncio
async def test_seeded_suite_covers_all_six_personas():
    first = await generate_suite(demo_spec(), MockProvider(), per_persona=4, seed=42)
    second = await generate_suite(demo_spec(), MockProvider(), per_persona=4, seed=42)
    assert first == second
    assert len(first.scenarios) == 24
    assert {s.persona for s in first.scenarios} == set(PERSONAS)
    assert all(len(s.turns) == 3 for s in first.scenarios)
    assert len({s.id for s in first.scenarios}) == 24
    assert any("Español" in turn for s in first.scenarios for turn in s.turns)
    changed = await generate_suite(demo_spec(), MockProvider(), per_persona=4, seed=43)
    assert first != changed


@pytest.mark.parametrize("count", [0, -1, 101])
@pytest.mark.asyncio
async def test_scenario_count_is_bounded(count):
    with pytest.raises(ValueError, match="per_persona"):
        await generate_suite(demo_spec(), MockProvider(), per_persona=count, seed=1)


@pytest.mark.asyncio
async def test_missing_persona_from_model_is_rejected():
    class IncompleteProvider:
        name = "bad"

        async def chat(self, messages, **kwargs):
            return Reply(content=json.dumps({"scenarios": [{"persona": "angry", "objective": "test", "turns": ["hi"]}]}))

    with pytest.raises(ValueError, match="persona"):
        await generate_suite(demo_spec(), IncompleteProvider(), per_persona=1, seed=1)


@pytest.mark.asyncio
async def test_mock_refuses_general_quality_claims():
    spec = demo_spec().model_copy(update={"name": "Different agent"})
    with pytest.raises(ValueError, match="bundled demo"):
        await generate_suite(spec, MockProvider(), per_persona=1, seed=1)
