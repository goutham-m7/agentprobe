"""Portable, script-free HTML and injection-safe markdown for code review."""

from html import escape

from agentprobe.comparison import Comparison
from agentprobe.models import CRITERIA, PERSONAS, Run


def md(value) -> str:
    return (
        escape(str(value), quote=False)
        .replace("|", "&#124;")
        .replace("`", "&#96;")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def summarize(run: Run) -> dict:
    scored = [conversation for conversation in run.conversations if conversation.grades is not None]
    passed = sum(
        all(grade.passed for grade in conversation.grades.scores.values())
        for conversation in scored
    )
    return {
        "total": len(run.conversations),
        "scored": len(scored),
        "errors": len(run.conversations) - len(scored),
        "passed": passed,
        "rate": passed / len(scored) if scored else None,
        "criteria": {
            key: sum(conversation.grades.scores[key].passed for conversation in scored)
            / len(scored)
            if scored
            else None
            for key in CRITERIA
        },
    }


def percent(value) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def run_markdown(run: Run) -> str:
    summary = summarize(run)
    lines = [
        f"## agentprobe · {md(run.agent)}",
        "",
        f"**{percent(summary['rate'])}** conversation pass rate among {summary['scored']} scored; **{summary['errors']} errors**.",
        f"Judge: {md(run.judge)} · {summary['total']} conversations · {run.duration_seconds:.3f}s · concurrency {run.concurrency}",
        "",
        "| Criterion | Pass rate |",
        "|---|---:|",
    ]
    lines += [f"| {key} | {percent(rate)} |" for key, rate in summary["criteria"].items()]
    lines += ["", "### Failure evidence", ""]
    for conversation in run.conversations:
        if conversation.error:
            lines.append(f"- {md(conversation.scenario_id)}: **ERROR** {md(conversation.error)}")
        elif any(not grade.passed for grade in conversation.grades.scores.values()):
            for key, grade in conversation.grades.scores.items():
                if not grade.passed:
                    lines.append(
                        f"- {md(conversation.scenario_id)} / {key}: {md(grade.reason)} — “{md(grade.evidence)}”"
                    )
    if run.judge.startswith("mock:"):
        lines += [
            "",
            "Offline demo: deterministic domain-specific oracle, not measured general LLM judge quality.",
        ]
    return "\n".join(lines) + "\n"


def comparison_markdown(comparison: Comparison) -> str:
    lines = [
        "## agentprobe regression check",
        "",
        "**Significant regressions: " + ", ".join(comparison.regressions) + "**"
        if comparison.regressions
        else "**No significant regressions.**",
        "",
        f"{comparison.n} paired conversations · {comparison.bootstrap_samples:,} bootstrap resamples · seed {comparison.seed} · 95% percentile intervals",
        "",
        "| Criterion | Baseline | Candidate | Delta | 95% CI | Result |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for key, metric in comparison.metrics.items():
        interval = metric.interval
        lines.append(
            f"| {key} | {metric.baseline:.1%} | {metric.candidate:.1%} | {interval.delta * 100:+.1f} pp | [{interval.ci_low * 100:+.1f}, {interval.ci_high * 100:+.1f}] pp | {'REGRESSION' if interval.regressed else '—'} |"
        )
    lines += ["", *[f"- {md(warning)}" for warning in comparison.warnings]]
    return "\n".join(lines) + "\n"


STYLE = """
:root{color-scheme:light;--ink:#182638;--muted:#586879;--line:#dbe3e9;--accent:#b74613;--paper:#f3f6f8}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 ui-sans-serif,system-ui,sans-serif}
main{max-width:1180px;margin:auto;padding:48px 28px}header{border-top:5px solid var(--accent);padding:30px 0 24px}h1{font-size:46px;letter-spacing:-2px;margin:8px 0}h2{margin-top:36px;font-size:23px}p{max-width:85ch}.eyebrow{text-transform:uppercase;letter-spacing:3px;font:700 12px ui-monospace,monospace;color:var(--accent)}
.muted{color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}.card{background:white;padding:22px;border:1px solid var(--line);border-radius:10px}.value{display:block;font-size:32px;font-weight:750;letter-spacing:-1px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:13px 16px;text-align:left;border-bottom:1px solid var(--line)}th{font-size:12px;text-transform:uppercase;letter-spacing:1px;color:var(--muted)}.pass{color:#176846}.fail{color:#a32b22;font-weight:700}details{background:white;border:1px solid var(--line);border-radius:10px;margin:12px 0;padding:16px 20px}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f4f7;padding:15px;border-radius:6px;font:13px/1.6 ui-monospace,monospace}.role{text-transform:uppercase;font:700 11px ui-monospace,monospace;color:var(--muted)}.notice{border-left:4px solid var(--accent);background:#fff4e9;padding:14px 20px}a{color:#964015}footer{border-top:1px solid var(--line);margin-top:36px;padding-top:18px;color:var(--muted)}.scroll{overflow-x:auto}
@media(max-width:700px){main{padding:24px 16px}.cards{grid-template-columns:repeat(2,1fr)}h1{font-size:36px}td,th{padding:10px}}
"""


def page(title: str, body: str) -> str:
    return f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><title>{escape(title)}</title><style>{STYLE}</style></head><body><main>{body}<footer>agentprobe · local-first agent evaluation · no scripts, fonts or analytics loaded</footer></main></body></html>'


def render_html(run: Run) -> str:
    summary = summarize(run)
    body = f'<header><div class="eyebrow">agentprobe / evaluation dossier</div><h1>{escape(run.spec.name)}</h1><p class="muted">Agent: {escape(run.agent)} · Judge: {escape(run.judge)}<br>Run {escape(run.id)} · {escape(run.created_at)}</p></header>'
    if run.judge.startswith("mock:"):
        body += '<p class="notice">Offline synthetic demo. A transparent rule oracle scores this domain; these are not general LLM quality measurements.</p>'
    body += '<section class="cards" aria-label="Run metrics">'
    for label, value in [
        ("Conversation pass rate", percent(summary["rate"])),
        ("Scored / total", f"{summary['scored']} / {summary['total']}"),
        ("Execution errors", summary["errors"]),
        ("Wall time", f"{run.duration_seconds:.3f}s"),
    ]:
        body += f'<div class="card"><span class="value">{value}</span><span class="muted">{label}</span></div>'
    body += '</section><h2>Rubric scorecard</h2><p class="muted">Pass rates use scored conversations only. Any execution error makes a comparison ineligible.</p><table><thead><tr><th>Criterion</th><th>Pass rate</th></tr></thead><tbody>'
    for key, rate in summary["criteria"].items():
        body += f"<tr><td>{key.replace('_', ' ').title()}</td><td>{percent(rate)}</td></tr>"
    body += "</tbody></table><h2>Persona coverage</h2><table><thead><tr><th>Persona</th><th>Conversations</th><th>Passed</th></tr></thead><tbody>"
    scenarios = {scenario.id: scenario for scenario in run.suite.scenarios}
    for persona in PERSONAS:
        conversations = [
            conversation
            for conversation in run.conversations
            if scenarios[conversation.scenario_id].persona == persona
        ]
        passed = sum(
            conversation.grades is not None
            and all(grade.passed for grade in conversation.grades.scores.values())
            for conversation in conversations
        )
        body += f"<tr><td>{persona}</td><td>{len(conversations)}</td><td>{passed}</td></tr>"
    body += '</tbody></table><h2>Conversation evidence</h2><p class="muted">Expand a trial to inspect user turns, assistant replies, attempted tools and judge evidence.</p>'
    for conversation in run.conversations:
        scenario = scenarios[conversation.scenario_id]
        status = (
            "ERROR"
            if conversation.error
            else "PASS"
            if all(grade.passed for grade in conversation.grades.scores.values())
            else "FAIL"
        )
        body += f'<details><summary><span class="{"pass" if status == "PASS" else "fail"}">{status}</span> · {escape(scenario.persona)} · {escape(scenario.id)}</summary><p>{escape(scenario.objective)}</p>'
        if conversation.error:
            body += f'<p class="fail">{escape(conversation.error)}</p>'
        for message in conversation.messages:
            if message.role == "system":
                continue
            body += f'<div class="role">{message.role}</div><pre>{escape(message.content)}</pre>'
            for call in message.tool_calls:
                body += (
                    f"<pre>Attempted tool (not executed): {escape(call.model_dump_json())}</pre>"
                )
        if conversation.grades:
            body += "<table><thead><tr><th>Criterion</th><th>Result / reason / quoted evidence</th></tr></thead><tbody>"
            for key, grade in conversation.grades.scores.items():
                body += f'<tr><td>{key}</td><td><strong class="{"pass" if grade.passed else "fail"}">{"PASS" if grade.passed else "FAIL"}</strong> {escape(grade.reason)}<br><q>{escape(grade.evidence)}</q></td></tr>'
            body += "</tbody></table>"
        body += "</details>"
    return page(f"agentprobe — {run.spec.name}", body)


def comparison_html(comparison: Comparison) -> str:
    body = '<header><div class="eyebrow">agentprobe / version comparison</div><h1>Catch the quiet regressions.</h1></header>'
    body += (
        '<p class="notice">'
        + (
            f"{len(comparison.regressions)} significant metric regressions detected."
            if comparison.regressions
            else "No significant regressions detected."
        )
        + "</p>"
    )
    body += f"<p>{comparison.n} paired conversations · {comparison.bootstrap_samples:,} resamples · 95% percentile confidence intervals</p>"
    body += '<div class="scroll"><table><thead><tr><th>Metric</th><th>Baseline</th><th>Candidate</th><th>Delta</th><th>95% CI</th></tr></thead><tbody>'
    for key, metric in comparison.metrics.items():
        interval = metric.interval
        body += f'<tr><td>{escape(key)}</td><td>{metric.baseline:.1%}</td><td>{metric.candidate:.1%}</td><td class="{"fail" if interval.regressed else "pass"}">{interval.delta * 100:+.1f} pp</td><td>[{interval.ci_low * 100:+.1f}, {interval.ci_high * 100:+.1f}] pp</td></tr>'
    body += "</tbody></table></div>"
    body += "".join(f'<p class="muted">{escape(warning)}</p>' for warning in comparison.warnings)
    return page("agentprobe — regression comparison", body)
