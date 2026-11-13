from importlib.metadata import distribution, version
from importlib.resources import files

from agentprobe import __version__
from agentprobe.spec import load_spec


def test_distribution_version_and_bundled_contract():
    assert __version__ == version("agentprobe") == "0.2.0"
    assert distribution("agentprobe").metadata["License-Expression"] == "MIT"
    assert load_spec(files("agentprobe").joinpath("data/harbor.yaml")).name == "Harbor Outfitters"
    assert files("agentprobe").joinpath("data/reference-labels.json").is_file()
    assert any(
        entry.name == "agentprobe" and entry.value == "agentprobe.cli:main"
        for entry in distribution("agentprobe").entry_points
    )
