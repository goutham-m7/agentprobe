import json
from importlib.resources import files

from test_providers import completion, endpoint

from agentprobe.cli import main
from agentprobe.demo_agents import demo_spec
from agentprobe.judge import Judge
from agentprobe.mock import MockProvider
from agentprobe.models import CRITERIA, Message, Reply
from agentprobe.scenarios import generate_suite


def invoke(monkeypatch, *args):
    monkeypatch.setattr("sys.argv", ["agentprobe", *map(str, args)])
    return main()


def test_calibrate_cli_writes_provenance_and_all_reports(tmp_path, monkeypatch, capsys):
    labels = files("agentprobe").joinpath("data/reference-labels.json")
    out = tmp_path / "calibration"
    assert invoke(monkeypatch, "calibrate", labels, "--provider", "mock", "--out", out) == 0
    assert "against synthetic reference labels" in capsys.readouterr().out
    assert (
        json.loads((out / "calibration.json").read_text())["label_source"] == "synthetic_reference"
    )
    assert (out / "report.html").is_file()
    assert (out / "summary.md").is_file()


def test_run_cli_with_real_local_http_target(tmp_path, monkeypatch):
    spec = files("agentprobe").joinpath("data/harbor.yaml")
    with endpoint(
        completion({"content": "Unopened items can be returned within 30 days with a receipt."})
    ) as (url, received):
        assert (
            invoke(
                monkeypatch,
                "run",
                spec,
                "--provider",
                "mock",
                "--endpoint",
                url,
                "--target-model",
                "local",
                "--per-persona",
                1,
                "--out",
                tmp_path / "http",
            )
            == 0
        )
    assert len(received) == 18
    assert len(received[-1][2]["messages"]) == 6


def test_run_cli_keeps_http_errors_in_artifacts(tmp_path, monkeypatch):
    spec = files("agentprobe").joinpath("data/harbor.yaml")
    out = tmp_path / "failed"
    with endpoint({"error": "private"}, 401) as (url, _):
        assert (
            invoke(
                monkeypatch,
                "run",
                spec,
                "--provider",
                "mock",
                "--endpoint",
                url,
                "--target-model",
                "local",
                "--per-persona",
                1,
                "--out",
                out,
            )
            == 2
        )
    run = json.loads((out / "run.json").read_text())
    assert all(item["grades"] is None and item["error"] for item in run["conversations"])
    assert "private" not in (out / "run.json").read_text()


def test_generate_cli_with_real_local_model_endpoint(tmp_path, monkeypatch):
    import asyncio

    suite = asyncio.run(generate_suite(demo_spec(), MockProvider(), per_persona=1, seed=42))
    response = {"scenarios": [scenario.model_dump(exclude={"id"}) for scenario in suite.scenarios]}
    with endpoint(completion({"content": json.dumps(response)})) as (url, _):
        assert (
            invoke(
                monkeypatch,
                "generate",
                files("agentprobe").joinpath("data/harbor.yaml"),
                "--provider",
                "openai",
                "--base-url",
                url,
                "--model",
                "local-model",
                "--per-persona",
                1,
                "--out",
                tmp_path / "suite.json",
            )
            == 0
        )


async def test_judge_rejects_duplicate_rubric_keys():
    scores = {key: {"passed": True, "reason": "ok", "evidence": "hello"} for key in CRITERIA}
    text = json.dumps({"scores": scores})
    text = text.replace(
        '"scores": {',
        '"scores": {"tone": {"passed": false, "reason": "bad", "evidence": "hello"},',
        1,
    )

    class Duplicate:
        name = "duplicate"

        async def chat(self, messages, **kwargs):
            return Reply(content=text)

    import pytest

    with pytest.raises(ValueError, match="duplicate"):
        await Judge(Duplicate()).score(
            demo_spec(), [Message(role="assistant", content="hello")], "Help"
        )
