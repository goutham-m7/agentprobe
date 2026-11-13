"""Blind, all-or-nothing human annotation of local run evidence."""

from agentprobe.calibration import LabelledExample, LabelSet
from agentprobe.models import CRITERIA, Run


def label_run(run: Run, labeler: str) -> LabelSet:
    if not labeler.strip():
        raise ValueError("A nonempty labeler is required")
    if any(
        c.error or not any(m.role == "assistant" for m in c.messages) for c in run.conversations
    ):
        raise ValueError("Labelling requires complete transcripts without execution errors")
    examples = []
    for scenario, conversation in zip(run.suite.scenarios, run.conversations, strict=True):
        print(f"\nScenario: {scenario.id}\nObjective: {scenario.objective}")
        for message in conversation.messages:
            # repr prevents terminal escape sequences from acting as controls.
            print(f"{message.role}: {message.content!r}")
            for call in message.tool_calls:
                print(f"Attempted tool: {call.model_dump_json()}")
        labels = {}
        for criterion in CRITERIA:
            while True:
                try:
                    answer = input(f"{criterion} [pass/fail]: ").strip().lower()
                except EOFError:
                    raise ValueError("Annotation interrupted; no label file written") from None
                if answer in {"pass", "fail"}:
                    labels[criterion] = answer == "pass"
                    break
                print("Enter pass or fail; no annotation is inferred.")
        examples.append(
            LabelledExample(
                id=scenario.id,
                objective=scenario.objective,
                messages=conversation.messages,
                labels=labels,
            )
        )
    return LabelSet(label_source="human", labeler=labeler, spec=run.spec, examples=examples)
