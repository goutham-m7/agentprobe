"""Original synthetic demo domain; no customer or employer material."""

from importlib.resources import files

from agentprobe.models import AgentSpec
from agentprobe.spec import load_spec


def demo_spec() -> AgentSpec:
    return load_spec(files("agentprobe").joinpath("data/harbor.yaml"))
