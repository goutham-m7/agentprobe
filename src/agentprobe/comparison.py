"""Compare identical suites and judges; never hide infrastructure failures."""

from typing import Literal

from agentprobe.models import CRITERIA, Model, Run
from agentprobe.statistics import Bootstrap, bootstrap_delta


class MetricDiff(Model):
    baseline: float
    candidate: float
    interval: Bootstrap


class Comparison(Model):
    format_version: Literal[1] = 1
    baseline_id: str
    candidate_id: str
    n: int
    seed: int
    bootstrap_samples: int
    confidence: float = 0.95
    metrics: dict[str, MetricDiff]
    regressions: list[str]
    warnings: list[str]


def compare(baseline: Run, candidate: Run, *, samples: int, seed: int) -> Comparison:
    if baseline.suite != candidate.suite or baseline.spec != candidate.spec:
        raise ValueError("Comparisons require the exact same suite and spec; reuse --suite")
    if baseline.judge != candidate.judge:
        raise ValueError("Comparisons require the same judge identity")
    if any(conversation.error is not None for run in [baseline, candidate] for conversation in run.conversations):
        raise ValueError("Cannot compare incomplete runs: resolve agent/judge errors first")
    metrics = {}
    for criterion in ["overall", *CRITERIA]:
        def values(run):
            return [int(all(grade.passed for grade in conversation.grades.scores.values()))
                    if criterion == "overall" else int(conversation.grades.scores[criterion].passed)
                    for conversation in run.conversations]
        left, right = values(baseline), values(candidate)
        interval = bootstrap_delta([float(b - a) for a, b in zip(left, right, strict=True)], samples=samples, seed=seed)
        metrics[criterion] = MetricDiff(baseline=sum(left)/len(left), candidate=sum(right)/len(right), interval=interval)
    warnings = ["Intervals are paired conversation-level percentile bootstrap; unadjusted for multiple comparisons.",
                "Intervals describe this empirical suite, not all users; related templates can reduce effective sample size."]
    if len(baseline.conversations) < 20:
        warnings.append("Small sample: fewer than 20 paired conversations.")
    return Comparison(baseline_id=baseline.id, candidate_id=candidate.id,
                      n=len(baseline.conversations), seed=seed, bootstrap_samples=samples,
                      metrics=metrics, regressions=[key for key, metric in metrics.items() if metric.interval.regressed],
                      warnings=warnings)
