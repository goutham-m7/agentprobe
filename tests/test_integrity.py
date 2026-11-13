import json

import httpx
import pytest
from pydantic import ValidationError
from test_providers import completion, endpoint

from agentprobe.adapters import CallableAgent
from agentprobe.cli import main
from agentprobe.models import Conversation, Run
from agentprobe.providers import OpenAIProvider, ProviderError
from agentprobe.spec import load_spec


@pytest.mark.parametrize(
    "payload", [[], {"choices": ["bad"]}, {"choices": [{"finish_reason": "stop", "message": []}]}]
)
async def test_http_malformed_objects_fail_safely(payload):
    with endpoint(payload) as (url, _):
        async with httpx.AsyncClient(trust_env=False) as client:
            with pytest.raises(ProviderError):
                await OpenAIProvider(client, url, "", "m").chat([])


async def test_http_transport_failure_is_safe():
    with endpoint(completion({"content": "ok"})) as (url, _):
        pass
    async with httpx.AsyncClient(trust_env=False, timeout=1) as client:
        with pytest.raises(ProviderError, match="transport"):
            await OpenAIProvider(client, url, "private-key", "m").chat([])


def test_endpoint_identity_prevents_cross_provider_judge_comparison():
    first = OpenAIProvider(None, "http://one.local/v1", "a", "same-model")
    second = OpenAIProvider(None, "http://two.local/v1", "b", "same-model")
    assert first.name != second.name
    assert (
        first.name
        == OpenAIProvider(
            None, "http://one.local/v1/chat/completions", "different-key", "same-model"
        ).name
    )
    assert "http" not in first.name


def test_duplicate_yaml_fields_fail_closed(tmp_path):
    path = tmp_path / "spec.yaml"
    path.write_text("name: first\nname: second\npurpose: help\npolicies: [safe]\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_spec(path)


def test_run_json_cannot_omit_or_reorder_trials(completed_run):
    data = completed_run.model_dump()
    data["conversations"] = list(reversed(data["conversations"]))
    with pytest.raises(ValidationError, match="every suite scenario"):
        Run.model_validate(data)
    data = completed_run.model_dump()
    data["spec"]["name"] = "changed"
    with pytest.raises(ValidationError, match="fingerprint"):
        Run.model_validate(data)


def test_error_and_grade_are_mutually_exclusive(completed_run):
    data = completed_run.conversations[0].model_dump()
    data["error"] = "failed"
    with pytest.raises(ValidationError, match="either"):
        Conversation.model_validate(data)


async def test_sync_callable_can_return_an_awaitable():
    async def answer():
        return "hello"

    reply = await CallableAgent(lambda _: answer(), "callable-object").respond([], [])
    assert reply.content == "hello"


def test_cli_refuses_existing_output_before_import_or_paid_calls(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["agentprobe", "run", "missing.yaml", "--callable", "missing:call", "--out", str(tmp_path)],
    )
    assert main() == 2
    assert "Refusing to overwrite" in capsys.readouterr().err


def test_cli_calibration_requires_filled_human_labels(tmp_path, monkeypatch, capsys):
    from importlib.resources import files

    labels = json.loads(files("agentprobe").joinpath("data/reference-labels.json").read_text())
    labels["label_source"] = "human"
    labels["examples"][0]["labels"]["tone"] = None
    path = tmp_path / "unlabelled.json"
    path.write_text(json.dumps(labels))
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentprobe",
            "calibrate",
            str(path),
            "--provider",
            "mock",
            "--out",
            str(tmp_path / "output"),
        ],
    )
    assert main() == 2
    assert "valid boolean" in capsys.readouterr().err
