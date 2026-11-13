from xml.etree import ElementTree as ET

from agentprobe.artifacts import write_run
from agentprobe.demo_agents import demo_spec
from agentprobe.models import (
    CRITERIA,
    Conversation,
    Grades,
    Judgment,
    Message,
    Run,
    Scenario,
    Suite,
)


def test_runs_export_real_junit_with_distinct_failures_and_errors(tmp_path):
    spec = demo_spec()
    suite = Suite(
        spec_fingerprint=spec.fingerprint,
        seed=1,
        scenarios=[
            Scenario(id=name, persona="angry", objective="Help", turns=["Hi"])
            for name in ["pass", "fail<&\x01", "error"]
        ],
    )
    grades = Grades(
        scores={key: Judgment(passed=True, reason="supported", evidence="ok") for key in CRITERIA}
    )
    failed = grades.model_copy(deep=True)
    failed.scores["tone"] = Judgment(passed=False, reason="Rude <&\x01", evidence="bad & reply")
    run = Run(
        id="junit",
        agent="target<&",
        judge="judge",
        created_at="now",
        spec=spec,
        suite=suite,
        concurrency=1,
        duration_seconds=1.5,
        conversations=[
            Conversation(
                scenario_id=suite.scenarios[i].id,
                messages=[Message(role="assistant", content="ok")],
                grades=grade,
                error=error,
                duration_seconds=0.5,
            )
            for i, (grade, error) in enumerate(
                [(grades, None), (failed, None), (None, "Timeout <&\x01")]
            )
        ],
    )
    out = tmp_path / "run"
    write_run(run, out)
    xml = ET.parse(out / "junit.xml").getroot()
    assert xml.tag == "testsuite"
    assert xml.attrib["tests"] == "3"
    assert xml.attrib["failures"] == "1"
    assert xml.attrib["errors"] == "1"
    cases = xml.findall("testcase")
    assert len(cases) == 3
    assert cases[0].find("failure") is None
    assert cases[1].attrib["name"] == "fail<&"
    assert "tone" in cases[1].find("failure").text
    assert "Rude <&" in cases[1].find("failure").text
    assert "bad & reply" in cases[1].find("failure").text
    assert cases[2].find("error").text == "Timeout <&"
    assert float(cases[0].attrib["time"]) == 0.5
