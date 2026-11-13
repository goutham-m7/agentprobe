"""Observed score instability across identical repeated trials, not a probability guarantee."""

from statistics import fmean, variance

from agentprobe.models import CRITERIA, Run


def _metric(values: list[bool], errors: int) -> dict:
    return {
        "passed": sum(values),
        "failed": len(values) - sum(values),
        "pass_rate": fmean(values) if not errors else None,
        "variance": variance(values) if not errors else None,
        "flaky": len(set(values)) > 1,
    }


def analyze_runs(runs: list[Run]) -> dict:
    if not 2 <= len(runs) <= 100:
        raise ValueError("repeats must be 2..100")
    first = runs[0]
    if any(
        run.spec != first.spec
        or run.suite != first.suite
        or run.judge != first.judge
        or run.agent != first.agent
        for run in runs
    ):
        raise ValueError("Flakiness requires identical spec, suite, target and judge")
    if len({run.id for run in runs}) != len(runs):
        raise ValueError("Flakiness requires distinct run IDs")
    scenarios = []
    for index, scenario in enumerate(first.suite.scenarios):
        conversations = [run.conversations[index] for run in runs]
        errors = sum(c.error is not None for c in conversations)
        grades = [c.grades for c in conversations if c.grades is not None]
        row = {
            "scenario_id": scenario.id,
            "errors": errors,
            **_metric([all(g.passed for g in grade.scores.values()) for grade in grades], errors),
            "criteria": {
                key: _metric([grade.scores[key].passed for grade in grades], errors)
                for key in CRITERIA
            },
        }
        # A rubric can flip even when some other rubric always fails overall.
        row["flaky"] = row["flaky"] or any(m["flaky"] for m in row["criteria"].values())
        scenarios.append(row)
    return {
        "format_version": 1,
        "repeats": len(runs),
        "run_ids": [run.id for run in runs],
        "agent": first.agent,
        "judge": first.judge,
        "flaky_scenarios": sum(row["flaky"] for row in scenarios),
        "errors": sum(row["errors"] for row in scenarios),
        "scenarios": scenarios,
    }


def flakiness_markdown(result: dict) -> str:
    lines = [
        "# Observed flakiness",
        "",
        f"{result['repeats']} repeats; {result['flaky_scenarios']}/{len(result['scenarios'])} scenarios varied; {result['errors']} errors.",
        "",
        "| Scenario | Pass rate | Sample variance | Errors | Varied criteria |",
        "|---|---:|---:|---:|---|",
    ]
    for row in result["scenarios"]:
        name = row["scenario_id"].replace("|", "\\|").replace("\n", " ")
        rate = "incomplete" if row["pass_rate"] is None else f"{row['pass_rate']:.1%}"
        var = "undefined" if row["variance"] is None else f"{row['variance']:.4f}"
        varied = (
            ", ".join(key for key, value in row["criteria"].items() if value["flaky"]) or "none"
        )
        lines.append(f"| {name} | {rate} | {var} | {row['errors']} | {varied} |")
    lines += [
        "",
        "Variance uses binary all-criteria success. Any execution error suppresses that scenario's rates and variances. Flips include per-criterion changes. No observed flip is not proof of determinism; target and judge randomness are not separated.",
    ]
    return "\n".join(lines) + "\n"
