"""Small, explicit estimators: binary Cohen's kappa and paired percentile bootstrap."""

import math
import random
from statistics import fmean

from agentprobe.models import Model


class Agreement(Model):
    n: int
    agreement: float
    kappa: float | None
    warnings: list[str]


def agreement(reference: list[bool], predicted: list[bool]) -> Agreement:
    if not reference or len(reference) != len(predicted):
        raise ValueError("Agreement needs equal nonempty paired labels")
    if any(type(value) is not bool for value in reference + predicted):
        raise ValueError("Agreement labels must be booleans")
    n = len(reference)
    observed = sum(left == right for left, right in zip(reference, predicted, strict=True)) / n
    ref_positive = sum(reference) / n
    pred_positive = sum(predicted) / n
    expected = ref_positive * pred_positive + (1 - ref_positive) * (1 - pred_positive)
    kappa = None if expected == 1 else (observed - expected) / (1 - expected)
    warnings = []
    if n < 20:
        warnings.append("small_sample")
    if kappa is None:
        warnings.append("undefined_kappa")
    elif kappa < 0.6:
        warnings.append("low_kappa")
    if observed < 0.8:
        warnings.append("low_agreement")
    return Agreement(n=n, agreement=observed, kappa=kappa, warnings=warnings)


class Bootstrap(Model):
    delta: float
    ci_low: float
    ci_high: float
    regressed: bool


def _percentile(sorted_values: list[float], fraction: float) -> float:
    index = (len(sorted_values) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (index - lower)


def bootstrap_delta(deltas: list[float], *, seed: int, samples: int) -> Bootstrap:
    if len(deltas) < 2 or not 100 <= samples <= 100000:
        raise ValueError("Bootstrap needs at least 2 pairs and 100..100000 samples")
    if any(not math.isfinite(value) or not -1 <= value <= 1 for value in deltas):
        raise ValueError("Paired deltas must be finite and between -1 and 1")
    rng = random.Random(seed)
    n = len(deltas)
    estimates = sorted(fmean(rng.choices(deltas, k=n)) for _ in range(samples))
    low, high = _percentile(estimates, 0.025), _percentile(estimates, 0.975)
    return Bootstrap(delta=fmean(deltas), ci_low=low, ci_high=high, regressed=high < 0)
