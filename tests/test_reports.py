import json

import pytest

from agentprobe.artifacts import read_run, write_run
from agentprobe.comparison import compare
from agentprobe.reports import comparison_markdown, render_html, run_markdown, summarize


def test_report_summarizes_failures(completed_run):
    summary = summarize(completed_run)
    assert summary["scored"] == 6
    assert summary["errors"] == 0
    assert summary["passed"] == 1
    assert summary["rate"] == pytest.approx(1 / 6)
    text = run_markdown(completed_run)
    assert "16.7%" in text
    assert "HARBOR-STAFF" in text
    assert "tool_misuse" in text


def test_html_escapes_all_untrusted_content(completed_run):
    completed_run.agent = '<script>alert("x")</script>'
    completed_run.conversations[0].messages[-1].content = "<img src=x onerror=alert(1)>"
    html = render_html(completed_run)
    assert "<script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img" in html
    assert '<html lang="en">' in html
    assert "<details" in html


def test_markdown_blocks_html_and_table_injection(completed_run):
    completed_run.agent = "<script>x</script>|oops\n# injected"
    text = run_markdown(completed_run)
    assert "<script>" not in text
    assert "&#124;" in text
    assert "\n# injected" not in text


def test_artifacts_roundtrip_and_refuse_overwrite(completed_run, tmp_path):
    directory = tmp_path / "run"
    write_run(completed_run, directory)
    assert read_run(directory) == completed_run
    assert read_run(directory / "run.json") == completed_run
    assert (directory / "report.html").stat().st_size > 1000
    assert json.loads((directory / "run.json").read_text())["format_version"] == 1
    with pytest.raises(FileExistsError):
        write_run(completed_run, directory)


def test_comparison_markdown_contains_method_and_delta(completed_run):
    result = compare(completed_run, completed_run, samples=100, seed=1)
    text = comparison_markdown(result)
    assert "95%" in text and "0.0 pp" in text
    assert "unadjusted" in text
    assert "No significant regressions" in text
