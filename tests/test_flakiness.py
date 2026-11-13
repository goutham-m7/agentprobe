import json
import os
import subprocess
import sys
from importlib.resources import files

import pytest

from agentprobe.adapters import CallableAgent
from agentprobe.demo_agents import demo_spec
from agentprobe.flakiness import analyze_runs
from agentprobe.judge import Judge
from agentprobe.mock import MockProvider
from agentprobe.models import Scenario, Suite
from agentprobe.runner import run_suite


async def runs():
    plan = Suite(
        spec_fingerprint=demo_spec().fingerprint,
        seed=1,
        scenarios=[Scenario(id="one", persona="angry", objective="Help politely", turns=["Hi"])],
    )
    outputs = iter(
        [
            "Unopened items can be returned within 30 days with a receipt.",
            "Learn to read.",
            "Unopened items can be returned within 30 days with a receipt.",
        ]
    )
    agent = CallableAgent(lambda _: next(outputs), "alternating")
    return [
        await run_suite(demo_spec(), plan, agent, Judge(MockProvider()), concurrency=1, timeout=2)
        for _ in range(3)
    ]


@pytest.mark.asyncio
async def test_alternating_scores_are_flaky_with_sample_variance():
    result = analyze_runs(await runs())
    row = result["scenarios"][0]
    assert result["flaky_scenarios"] == 1
    assert row["pass_rate"] == pytest.approx(2 / 3)
    assert row["variance"] == pytest.approx(1 / 3)
    assert row["criteria"]["tone"]["flaky"] is True
    assert row["errors"] == 0


@pytest.mark.asyncio
async def test_errors_are_not_silently_dropped_from_rates():
    data = await runs()
    data[0].conversations[0].grades = None
    data[0].conversations[0].error = "timeout"
    row = analyze_runs(data)["scenarios"][0]
    assert row["errors"] == 1
    assert row["pass_rate"] is None
    assert row["variance"] is None
    assert row["criteria"]["tone"]["pass_rate"] is None


@pytest.mark.asyncio
async def test_mismatched_and_insufficient_runs_rejected():
    data = await runs()
    with pytest.raises(ValueError):
        analyze_runs(data[:1])
    data[1].judge = "different judge"
    with pytest.raises(ValueError, match="identical"):
        analyze_runs(data)


def test_repeat_cli_runs_identical_suite_and_writes_evidence(tmp_path):
    out = tmp_path / "repeat"
    command = [
        sys.executable,
        "-m",
        "agentprobe",
        "repeat",
        str(files("agentprobe").joinpath("data/harbor.yaml")),
        "--callable",
        "agentprobe.demo_agents:good_agent",
        "--per-persona",
        "1",
        "--repeats",
        "3",
        "--fail-on-flaky",
        "--out",
        str(out),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "flakiness.json").read_text())
    assert report["repeats"] == 3
    assert report["flaky_scenarios"] == 0
    assert len(report["scenarios"]) == 6
    assert all(row["variance"] == 0 for row in report["scenarios"])
    assert len(list(out.glob("run-*/junit.xml"))) == 3
    assert "0/6" in result.stdout


@pytest.mark.parametrize("repeats", ["1", "101"])
def test_cli_rejects_repeat_bounds_before_running(tmp_path, repeats):
    out = tmp_path / "repeat"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agentprobe",
            "repeat",
            "missing.yaml",
            "--callable",
            "missing:target",
            "--repeats",
            repeats,
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "repeats must be 2..100" in result.stderr
    assert not out.exists()


@pytest.mark.parametrize("behavior,expected", [("flip", 1), ("error", 2)])
def test_repeat_cli_gates_flips_and_preserves_errors(tmp_path, behavior, expected):
    module = tmp_path / "target_fixture.py"
    if behavior == "flip":
        module.write_text(
            "calls = 0\n"
            "async def agent(messages):\n"
            "    global calls\n"
            "    calls += 1\n"
            "    return 'Learn to read.' if calls % 2 else 'Unopened items can be returned within 30 days with a receipt.'\n"
        )
    else:
        module.write_text("async def agent(messages):\n    raise RuntimeError('private')\n")
    suite = Suite(
        spec_fingerprint=demo_spec().fingerprint,
        seed=1,
        scenarios=[
            Scenario(id="one", persona="angry", objective="Help politely", turns=["Return?"])
        ],
    )
    source = tmp_path / "suite.json"
    source.write_text(suite.model_dump_json())
    out = tmp_path / "repeated"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agentprobe",
            "repeat",
            str(files("agentprobe").joinpath("data/harbor.yaml")),
            "--suite",
            str(source),
            "--callable",
            "target_fixture:agent",
            "--repeats",
            "3",
            "--fail-on-flaky",
            "--out",
            str(out),
        ],
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == expected, result.stderr
    report = json.loads((out / "flakiness.json").read_text())
    assert report["errors"] == (3 if behavior == "error" else 0)
    assert report["flaky_scenarios"] == (1 if behavior == "flip" else 0)
    assert "private" not in (out / "run-001/run.json").read_text()
