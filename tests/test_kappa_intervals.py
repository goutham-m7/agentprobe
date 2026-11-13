import json
import subprocess
import sys
from importlib.resources import files

import pytest

from agentprobe.statistics import bootstrap_agreement


def test_perfect_balanced_labels_and_undefined_replicates():
    result = bootstrap_agreement([[True], [False]], [[True], [False]], seed=4, samples=1000)
    assert result.kappa == 1
    assert result.ci_low == result.ci_high == 1
    assert 0 < result.bootstrap_undefined < 1000
    assert result.bootstrap_defined + result.bootstrap_undefined == 1000
    assert "undefined_bootstrap_replicates" in result.warnings


def test_degenerate_original_has_no_fabricated_interval():
    result = bootstrap_agreement([[True]] * 3, [[True]] * 3, seed=2, samples=100)
    assert result.kappa is None
    assert result.ci_low is result.ci_high is None
    assert result.bootstrap_undefined == 100


def test_cluster_bootstrap_keeps_rubric_decisions_together():
    ref = [[True, False]] * 10
    pred = [[True, False]] * 5 + [[False, True]] * 5
    result = bootstrap_agreement(ref, pred, seed=42, samples=1000)
    assert result == bootstrap_agreement(ref, pred, seed=42, samples=1000)
    assert result.kappa == 0
    assert result.ci_low < 0 < result.ci_high
    assert result.n == 20
    assert "small_sample" in result.warnings  # Ten independent transcripts, not 20 decisions.


@pytest.mark.parametrize(
    "ref,pred,samples",
    [
        ([], [], 100),
        ([[True]], [[True]], 99),
        ([[True]], [[True, False]], 100),
        ([[True]], [[1]], 100),
    ],
)
def test_invalid_bootstrap_inputs(ref, pred, samples):
    with pytest.raises(ValueError):
        bootstrap_agreement(ref, pred, seed=1, samples=samples)


def test_calibration_cli_persists_interval_settings(tmp_path):
    out = tmp_path / "calibration"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agentprobe",
            "calibrate",
            str(files("agentprobe").joinpath("data/reference-labels.json")),
            "--out",
            str(out),
            "--samples",
            "100",
            "--seed",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads((out / "calibration.json").read_text())
    assert data["bootstrap_samples"] == 100
    assert data["bootstrap_seed"] == 7
    assert "ci_low" in data["metrics"]["tone"]
    assert "95% kappa CI" in result.stdout
