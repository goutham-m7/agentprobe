import json

import pytest
from pydantic import ValidationError

from agentprobe.models import AgentSpec, Scenario, Suite
from agentprobe.spec import load_spec, rubric


def spec_data():
    return {"name": "Parcel Desk", "purpose": "Help track parcels", "policies": ["Never reveal secrets"],
            "facts": ["Refunds require a receipt"], "tools": [{"name": "track", "description": "Track a parcel"}]}


def test_spec_derives_five_grounded_criteria(tmp_path):
    path = tmp_path / "agent.yaml"
    path.write_text(json.dumps(spec_data()))
    spec = load_spec(path)
    criteria = rubric(spec)
    assert set(criteria) == {"task_success", "policy_adherence", "hallucination", "tone", "tool_misuse"}
    assert "track parcels" in criteria["task_success"]
    assert "Never reveal secrets" in criteria["policy_adherence"]
    assert "receipt" in criteria["hallucination"]
    assert "track" in criteria["tool_misuse"]


@pytest.mark.parametrize("patch", [{"name": ""}, {"purpose": " "}, {"policies": []}, {"extra": 1},
                                   {"tools": [{"name": "x", "description": "one"}, {"name": "x", "description": "two"}]}])
def test_spec_rejects_ambiguous_contracts(patch):
    with pytest.raises(ValidationError):
        AgentSpec.model_validate(spec_data() | patch)


def test_fingerprint_is_stable_and_changes_with_policy():
    spec = AgentSpec.model_validate(spec_data())
    assert spec.fingerprint == AgentSpec.model_validate(dict(reversed(list(spec_data().items())))).fingerprint
    assert spec.fingerprint != AgentSpec.model_validate(spec_data() | {"policies": ["New policy"]}).fingerprint


def test_suite_rejects_duplicate_ids():
    scenario = Scenario(id="s1", persona="confused", objective="Track", turns=["Where?"])
    with pytest.raises(ValidationError, match="unique"):
        Suite(spec_fingerprint="a" * 64, seed=7, scenarios=[scenario, scenario])


def test_bad_yaml_is_actionable(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("name: [")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_spec(path)
