"""Portable JUnit evidence: a conversation is a testcase, not a rubric item."""

from xml.etree import ElementTree as ET

from agentprobe.models import Run


def xml_text(value: str) -> str:
    return "".join(
        char
        for char in value
        if char in "\t\n\r"
        or 0x20 <= ord(char) <= 0xD7FF
        or 0xE000 <= ord(char) <= 0xFFFD
        or 0x10000 <= ord(char) <= 0x10FFFF
    )


def render_junit(run: Run) -> str:
    failures = sum(
        c.grades is not None and any(not g.passed for g in c.grades.scores.values())
        for c in run.conversations
    )
    root = ET.Element(
        "testsuite",
        name="agentprobe",
        tests=str(len(run.conversations)),
        failures=str(failures),
        errors=str(sum(c.error is not None for c in run.conversations)),
        time=f"{run.duration_seconds:.6f}",
    )
    for conversation in run.conversations:
        case = ET.SubElement(
            root,
            "testcase",
            name=xml_text(conversation.scenario_id),
            classname=xml_text(run.agent),
            time=f"{conversation.duration_seconds:.6f}",
        )
        if conversation.error:
            node = ET.SubElement(case, "error", message="Execution error", type="ExecutionError")
            node.text = xml_text(conversation.error)
        elif conversation.grades:
            failed = [
                (key, value)
                for key, value in conversation.grades.scores.items()
                if not value.passed
            ]
            if failed:
                node = ET.SubElement(
                    case, "failure", message="Rubric criteria failed", type="RubricFailure"
                )
                node.text = xml_text(
                    "\n".join(
                        f"{key}: {grade.reason}\nEvidence: {grade.evidence}"
                        for key, grade in failed
                    )
                )
    ET.indent(root)
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"
