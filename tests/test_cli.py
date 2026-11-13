import json
import subprocess
import sys

from agentprobe.models import Suite


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "agentprobe", *map(str, args)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_demo_end_to_end_and_ci_gate(tmp_path):
    directory = tmp_path / "demo"
    result = cli("demo", "--out", directory, "--samples", "1000")
    assert result.returncode == 0, result.stderr
    assert "Good: 24/24" in result.stdout
    assert "Broken: 4/24" in result.stdout
    assert "synthetic reference labels" in result.stdout
    assert (directory / "index.html").is_file()
    assert (directory / "good/report.html").is_file()
    assert (directory / "broken/summary.md").is_file()
    assert (directory / "calibration.json").is_file()
    comparison = json.loads((directory / "diff.json").read_text())
    assert "tone" in comparison["regressions"]
    gate = cli(
        "diff",
        directory / "good",
        directory / "broken",
        "--samples",
        "1000",
        "--fail-on-regression",
    )
    assert gate.returncode == 1
    clean = cli(
        "diff", directory / "good", directory / "good", "--samples", "100", "--fail-on-regression"
    )
    assert clean.returncode == 0


def test_generate_then_run_trusted_callable(tmp_path):
    from importlib.resources import files

    spec = files("agentprobe").joinpath("data/harbor.yaml")
    suite = tmp_path / "suite.json"
    result = cli("generate", spec, "--provider", "mock", "--out", suite, "--per-persona", "1")
    assert result.returncode == 0, result.stderr
    assert len(Suite.model_validate_json(suite.read_text()).scenarios) == 6
    result = cli(
        "run",
        spec,
        "--provider",
        "mock",
        "--suite",
        suite,
        "--callable",
        "agentprobe.demo_agents:good_agent",
        "--out",
        tmp_path / "run",
    )
    assert result.returncode == 0, result.stderr
    assert "6/6" in result.stdout


def test_bad_input_reports_clean_error(tmp_path):
    result = cli(
        "run", tmp_path / "missing.yaml", "--callable", "missing:func", "--provider", "mock"
    )
    assert result.returncode == 2
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_help_and_version():
    assert "CI for AI agents" in cli("--help").stdout
    assert "0.2.0" in cli("--version").stdout
