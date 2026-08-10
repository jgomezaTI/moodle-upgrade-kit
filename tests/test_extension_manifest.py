import re
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_extension_manifest_shape_and_commands():
    data = yaml.safe_load((ROOT / "extension.yml").read_text())
    assert data["schema_version"] == "1.0"
    assert data["extension"]["id"] == "moodle"
    assert data["requires"]["speckit_version"]
    commands = data["provides"]["commands"]
    assert len(commands) == 16
    for command in commands:
        assert re.fullmatch(r"speckit\.moodle\.[a-z0-9-]+", command["name"])
        file_path = ROOT / command["file"]
        assert file_path.exists()
        assert file_path.read_text().startswith("---\n")


def test_all_skill_contracts_exist():
    manifest = __import__('json').loads((ROOT / 'skills/manifest.json').read_text())
    assert manifest['count'] == 13
    for name in manifest['skills']:
        assert (ROOT / 'skills' / name / 'SKILL.md').exists()
