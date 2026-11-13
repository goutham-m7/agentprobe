import subprocess
import sys

import pytest

from agentprobe.adapters import CallableAgent
from agentprobe.artifacts import write_run
from agentprobe.calibration import LabelSet
from agentprobe.demo_agents import demo_spec, good_agent
from agentprobe.judge import Judge
from agentprobe.mock import MockProvider
from agentprobe.models import Scenario, Suite
from agentprobe.runner import run_suite


@pytest.fixture
async def run_directory(tmp_path):
    suite = Suite(
        spec_fingerprint=demo_spec().fingerprint,
        seed=1,
        scenarios=[
            Scenario(
                id="one",
                persona="confused",
                objective="Find return policy",
                turns=["Return policy?"],
            )
        ],
    )
    run = await run_suite(
        demo_spec(),
        suite,
        CallableAgent(good_agent, "target"),
        Judge(MockProvider()),
        concurrency=1,
        timeout=2,
    )
    # A judge reason must not be shown to the annotator.
    for grade in run.conversations[0].grades.scores.values():
        grade.reason = "PREDICTION_SECRET"
    directory = tmp_path / "run"
    write_run(run, directory)
    return directory


def label(source, out, answers):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "agentprobe",
            "label",
            str(source),
            "--labeler",
            "Test annotator (synthetic stdin)",
            "--out",
            str(out),
        ],
        input=answers,
        text=True,
        capture_output=True,
        timeout=30,
    )


def test_complete_labels_are_valid_and_predictions_are_hidden(run_directory, tmp_path):
    out = tmp_path / "labels.json"
    result = label(run_directory, out, "invalid\npass\nfail\npass\nfail\npass\n")
    assert result.returncode == 0, result.stderr
    labels = LabelSet.model_validate_json(out.read_text())
    assert labels.label_source == "human"
    assert labels.examples[0].labels["tone"] is False
    assert "PREDICTION_SECRET" not in result.stdout
    assert "Enter pass or fail" in result.stdout
    assert "Return policy?" in result.stdout
    assert label(run_directory, out, "").returncode == 2


def test_eof_leaves_no_partial_labels(run_directory, tmp_path):
    out = tmp_path / "labels.json"
    result = label(run_directory, out, "pass\n")
    assert result.returncode == 2
    assert not out.exists()
    assert "Traceback" not in result.stderr
