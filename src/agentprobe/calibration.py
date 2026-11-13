"""Judge agreement, with mandatory human vs synthetic-reference provenance."""

import asyncio
from typing import Literal

from pydantic import Field, StrictBool, model_validator

from agentprobe.judge import Judge
from agentprobe.models import CRITERIA, AgentSpec, Criterion, Message, Model, Text
from agentprobe.statistics import Agreement, bootstrap_agreement


class LabelledExample(Model):
    id: Text
    objective: Text
    messages: list[Message] = Field(min_length=2)
    labels: dict[Criterion, StrictBool]

    @model_validator(mode="after")
    def complete(self):
        if set(self.labels) != set(CRITERIA):
            raise ValueError("Every rubric criterion requires a boolean reference label")
        if not any(message.role == "assistant" for message in self.messages):
            raise ValueError("Labelled transcript must contain assistant output")
        return self


class LabelSet(Model):
    format_version: Literal[1] = 1
    label_source: Literal["human", "synthetic_reference"]
    labeler: Text
    spec: AgentSpec
    examples: list[LabelledExample] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({example.id for example in self.examples}) != len(self.examples):
            raise ValueError("Label example IDs must be unique")
        return self


class Calibration(Model):
    format_version: Literal[1] = 1
    judge: Text
    label_source: Literal["human", "synthetic_reference"]
    labeler: Text
    examples: int
    metrics: dict[str, Agreement]
    unreliable_items: list[str]
    bootstrap_seed: int = 42
    bootstrap_samples: int = 1000


async def calibrate(
    labels: LabelSet,
    judge: Judge,
    *,
    concurrency: int,
    timeout: float,
    seed: int = 42,
    samples: int = 1000,
) -> Calibration:
    if not 1 <= concurrency <= 256 or timeout <= 0:
        raise ValueError("concurrency must be 1..256 and timeout must be positive")
    if not 100 <= samples <= 100000:
        raise ValueError("Bootstrap samples must be 100..100000")
    semaphore = asyncio.Semaphore(concurrency)

    async def score(example):
        async with semaphore, asyncio.timeout(timeout):
            return await judge.score(labels.spec, example.messages, example.objective)

    predictions = await asyncio.gather(*(score(example) for example in labels.examples))
    metrics = {
        key: bootstrap_agreement(
            [[example.labels[key]] for example in labels.examples],
            [[prediction.scores[key].passed] for prediction in predictions],
            seed=seed,
            samples=samples,
        )
        for key in CRITERIA
    }
    metrics["overall"] = bootstrap_agreement(
        [[example.labels[key] for key in CRITERIA] for example in labels.examples],
        [[prediction.scores[key].passed for key in CRITERIA] for prediction in predictions],
        seed=seed,
        samples=samples,
    )
    return Calibration(
        judge=judge.name,
        label_source=labels.label_source,
        labeler=labels.labeler,
        examples=len(labels.examples),
        metrics=metrics,
        unreliable_items=[key for key in CRITERIA if metrics[key].warnings],
        bootstrap_seed=seed,
        bootstrap_samples=samples,
    )
