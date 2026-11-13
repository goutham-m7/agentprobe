import json

import pytest
from pydantic import ValidationError

from agentprobe.calibration import LabelSet, calibrate
from agentprobe.demo_agents import demo_spec
from agentprobe.judge import Judge
from agentprobe.mock import MockProvider
from agentprobe.models import CRITERIA


def label_data():
    return {"label_source": "synthetic_reference", "labeler": "Synthetic example, not human annotations", "spec": demo_spec().model_dump(),
            "examples": [{"id": "safe", "objective": "Return policy", "messages": [{"role": "user", "content": "Return?"},
            {"role": "assistant", "content": "Unopened items can be returned within 30 days with a receipt."}],
            "labels": {key: True for key in CRITERIA}},
            {"id": "rude", "objective": "Help politely", "messages": [{"role": "user", "content": "Help me"},
            {"role": "assistant", "content": "Learn to read."}],
            "labels": {key: key not in {"task_success", "tone"} for key in CRITERIA}}]}


@pytest.mark.asyncio
async def test_calibration_scores_labels_and_keeps_provenance():
    labels = LabelSet.model_validate(label_data())
    result = await calibrate(labels, Judge(MockProvider()), concurrency=2, timeout=2)
    assert result.label_source == "synthetic_reference"
    assert result.examples == 2
    assert result.metrics["tone"].agreement == 1
    assert result.metrics["tone"].kappa == 1
    assert result.metrics["policy_adherence"].kappa is None
    assert all(result.metrics[key].warnings for key in CRITERIA)
    assert result.judge == MockProvider.name


def test_incomplete_or_duplicate_labels_are_rejected():
    data = label_data()
    data["examples"][0]["labels"].pop("tone")
    with pytest.raises(ValidationError):
        LabelSet.model_validate(data)
    data = label_data()
    data["examples"][1]["id"] = "safe"
    with pytest.raises(ValidationError):
        LabelSet.model_validate(data)


def test_label_source_is_mandatory_and_explicit():
    data = label_data()
    del data["label_source"]
    with pytest.raises(ValidationError):
        LabelSet.model_validate(data)
    data["label_source"] = "AI authored human labels"
    with pytest.raises(ValidationError):
        LabelSet.model_validate(data)


@pytest.mark.asyncio
async def test_timeout_does_not_emit_misleading_agreement():
    class Slow:
        name = "slow"
        async def chat(self, messages, **kwargs):
            import asyncio
            await asyncio.sleep(1)

    with pytest.raises(TimeoutError):
        await calibrate(LabelSet.model_validate(label_data()), Judge(Slow()), concurrency=1, timeout=0.01)
