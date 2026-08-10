import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "moodle-upgrade-kit"


def test_codex_plugin_exposes_upgrade_moodle_skill_and_command():
    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    skill = (PLUGIN / "skills" / "upgrade-moodle" / "SKILL.md").read_text(encoding="utf-8")
    command = (PLUGIN / "commands" / "upgrade-moodle.md").read_text(encoding="utf-8")

    assert manifest["name"] == "moodle-upgrade-kit"
    assert manifest["version"].startswith("0.3.1")
    assert "name: upgrade-moodle" in skill
    assert "/upgrade-moodle" in skill
    assert "$upgrade-moodle" in command
    assert "Never create a commit" in skill
    assert "concise-clean-success" in skill
    assert "findings-and-outcomes" in skill
    assert "published_issue_count" in skill
    assert "TODO" not in skill


def test_local_marketplace_points_to_the_packaged_plugin():
    marketplace = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    entry = next(item for item in marketplace["plugins"] if item["name"] == "moodle-upgrade-kit")

    assert marketplace["name"] == "personal"
    assert entry["source"] == {"source": "local", "path": "./plugins/moodle-upgrade-kit"}
    assert entry["policy"]["installation"] == "AVAILABLE"


def test_upgrade_skill_ui_metadata_mentions_the_skill():
    metadata = yaml.safe_load((PLUGIN / "skills" / "upgrade-moodle" / "agents" / "openai.yaml").read_text(encoding="utf-8"))

    assert "$upgrade-moodle" in metadata["interface"]["default_prompt"]
