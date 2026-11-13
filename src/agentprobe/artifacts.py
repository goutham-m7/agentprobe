"""Versioned JSON evidence and static reports; never overwrite an existing run."""

from pathlib import Path

from agentprobe.models import Run
from agentprobe.reports import render_html, run_markdown


def read_run(path: Path) -> Run:
    source = path / "run.json" if path.is_dir() else path
    return Run.model_validate_json(source.read_text(encoding="utf-8"))


def write_run(run: Run, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "run.json").write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (directory / "report.html").write_text(render_html(run), encoding="utf-8")
    (directory / "summary.md").write_text(run_markdown(run), encoding="utf-8")
