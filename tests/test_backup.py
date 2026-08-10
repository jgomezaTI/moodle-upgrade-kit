from datetime import datetime, timezone

from moodle_upgrade.backup import verify_backups


def test_empty_backup_configuration_is_an_explicit_blocker():
    result = verify_backups(
        {
            "backup": {"paths": [], "required_components": []},
            "safety": {"max_backup_age_hours": 24},
        },
        now=datetime.now(timezone.utc),
    )

    codes = {finding["code"] for finding in result["findings"]}
    assert codes == {
        "BACKUP_LOCATIONS_NOT_CONFIGURED",
        "BACKUP_COMPONENTS_NOT_CONFIGURED",
    }
    assert result["summary"] == {
        "critical": 2,
        "warning": 0,
        "info": 0,
        "locations_configured": 0,
        "locations_accessible": 0,
        "components_required": 0,
        "components_verified": 0,
        "verified": False,
    }
