from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

BASE_REQUIRED_EXTENSIONS = {
    "iconv", "mbstring", "curl", "openssl", "ctype", "zip", "zlib",
    "simplexml", "spl", "pcre", "dom", "xml", "xmlreader", "intl",
    "json", "hash", "fileinfo",
}

DB_EXTENSION = {
    "mysql": "mysqli",
    "mariadb": "mysqli",
    "pgsql": "pgsql",
    "postgres": "pgsql",
    "postgresql": "pgsql",
    "mssql": "sqlsrv",
    "sqlserver": "sqlsrv",
    "oracle": "oci8",
}

DB_ALIASES = {
    "postgres": "pgsql",
    "postgresql": "pgsql",
    "sqlserver": "mssql",
    "microsoft sql server": "mssql",
    "aurora-mysql": "aurora_mysql",
    "aurora mysql": "aurora_mysql",
}

# Maintained from official Moodle release requirements. Keys are Moodle branches.
REQUIREMENTS: dict[str, dict[str, Any]] = {
    "3.9": {
        "upgrade_min": "3.5", "php_min": "7.2.0", "php_max": "7.4",
        "db_min": {"pgsql": "9.5", "mysql": "5.6", "mariadb": "10.2.29", "mssql": "2012", "oracle": "11.2"},
        "required_extensions": {"mbstring"}, "recommended_extensions": set(), "max_input_vars": None, "requires_64bit": False,
    },
    "3.11": {
        "upgrade_min": "3.6", "php_min": "7.3.0", "php_max": "8.0",
        "db_min": {"pgsql": "9.6", "mysql": "5.7", "mariadb": "10.2.29", "mssql": "2017", "oracle": "11.2"},
        "required_extensions": set(), "recommended_extensions": {"sodium"}, "max_input_vars": None, "requires_64bit": False,
    },
    "4.0": {
        "upgrade_min": "3.6", "php_min": "7.3.0", "php_max": "8.0",
        "db_min": {"pgsql": "10", "mysql": "5.7", "mariadb": "10.2.29", "mssql": "2017", "oracle": "11.2"},
        "required_extensions": set(), "recommended_extensions": {"sodium", "exif"}, "max_input_vars": None, "requires_64bit": False,
    },
    "4.1": {
        "upgrade_min": "3.9", "php_min": "7.4.0", "php_max": "8.1",
        "db_min": {"pgsql": "12", "mysql": "5.7", "mariadb": "10.4", "mssql": "2017", "oracle": "19"},
        "required_extensions": set(), "recommended_extensions": {"sodium", "exif"}, "max_input_vars": 5000,
        "max_input_vars_required_for_php8": True, "requires_64bit": False,
    },
    "4.2": {
        "upgrade_min": "3.11.8", "php_min": "8.0.0", "php_max": "8.2",
        "db_min": {"pgsql": "13", "mysql": "8.0", "mariadb": "10.6.7", "mssql": "2017", "oracle": "19"},
        "required_extensions": {"sodium"}, "recommended_extensions": {"exif"}, "max_input_vars": 5000, "requires_64bit": True,
    },
    "4.3": {
        "upgrade_min": "3.11.8", "php_min": "8.0.0", "php_max": "8.2",
        "db_min": {"pgsql": "13", "mysql": "8.0", "mariadb": "10.6.7", "mssql": "2017", "oracle": "19"},
        "required_extensions": {"sodium"}, "recommended_extensions": set(), "max_input_vars": 5000, "requires_64bit": True, "max_db_prefix": 10,
    },
    "4.4": {
        "upgrade_min": "4.1.2", "php_min": "8.1.0", "php_max": "8.3",
        "db_min": {"pgsql": "13", "mysql": "8.0", "mariadb": "10.6.7", "mssql": "2017", "oracle": "19"},
        "required_extensions": {"sodium"}, "recommended_extensions": set(), "max_input_vars": 5000, "requires_64bit": True, "max_db_prefix": 10,
    },
    "4.5": {
        "upgrade_min": "4.1.2", "php_min": "8.1.0", "php_max": "8.3",
        "db_min": {"pgsql": "13", "mysql": "8.0", "mariadb": "10.6.7", "aurora_mysql": "8.0", "mssql": "2017", "oracle": "19"},
        "required_extensions": {"sodium"}, "recommended_extensions": set(), "max_input_vars": 5000, "requires_64bit": True, "max_db_prefix": 10,
    },
    "5.0": {
        "upgrade_min": "4.2.3", "php_min": "8.2.0", "php_max": "8.4",
        "db_min": {"pgsql": "14", "mysql": "8.4", "mariadb": "10.11.0", "aurora_mysql": "8.0", "mssql": "2017"},
        "required_extensions": {"sodium"}, "recommended_extensions": set(), "max_input_vars": 5000, "requires_64bit": True, "max_db_prefix": 10,
    },
    "5.1": {
        "upgrade_min": "4.2.3", "php_min": "8.2.0", "php_max": "8.4",
        "db_min": {"pgsql": "15", "mysql": "8.4", "mariadb": "10.11.0", "aurora_mysql": "8.0", "mssql": "2017"},
        "required_extensions": {"sodium"}, "recommended_extensions": set(), "max_input_vars": 5000, "requires_64bit": True,
        "max_db_prefix": 10, "public_webroot": True,
    },
    "5.2": {
        "upgrade_min": "4.4", "php_min": "8.3.0", "php_max": "8.4",
        "db_min": {"pgsql": "16", "mysql": "8.4", "mariadb": "10.11.0", "aurora_mysql": "8.0", "mssql": "2019"},
        "required_extensions": {"sodium"}, "recommended_extensions": set(), "max_input_vars": 5000, "requires_64bit": True,
        "max_db_prefix": 10, "public_webroot": True,
    },
}


@dataclass
class Finding:
    severity: str
    code: str
    message: str


def _numbers(value: str | None) -> tuple[int, ...] | None:
    if value is None:
        return None
    match = re.search(r"(\d+(?:\.\d+){0,3})", str(value))
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _cmp(left: str | None, right: str | None) -> int | None:
    a = _numbers(left)
    b = _numbers(right)
    if a is None or b is None:
        return None
    size = max(len(a), len(b))
    a += (0,) * (size - len(a))
    b += (0,) * (size - len(b))
    return (a > b) - (a < b)


def _branch(value: str | None) -> str | None:
    nums = _numbers(value)
    if not nums or len(nums) < 2:
        return None
    return f"{nums[0]}.{nums[1]}"


def _version_from_line(line: str | None) -> str | None:
    nums = _numbers(line)
    return ".".join(map(str, nums)) if nums else None


def _normalise_driver(driver: str | None) -> str | None:
    if not driver:
        return None
    value = str(driver).strip().lower()
    return DB_ALIASES.get(value, value)


def _check(check_id: str, status: str, expected: Any, actual: Any, message: str) -> dict[str, Any]:
    return {"id": check_id, "status": status, "expected": expected, "actual": actual, "message": message}


def _serialise_requirements(req: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in req.items():
        if isinstance(value, set):
            result[key] = sorted(value)
        elif isinstance(value, dict):
            result[key] = dict(value)
        else:
            result[key] = value
    return result


def assess_compatibility(inventory: dict[str, Any], target_version: str | None = None) -> dict[str, Any]:
    findings: list[Finding] = []
    checks: list[dict[str, Any]] = []
    identity = inventory.get("identity", {})
    platform = inventory.get("platform", {})
    target = target_version or identity.get("target_version")
    target_branch = _branch(target)
    req = REQUIREMENTS.get(target_branch or "")

    if not req:
        findings.append(Finding("critical", "TARGET_REQUIREMENTS_UNKNOWN", f"No maintained requirement matrix entry exists for Moodle target {target!r}."))
        return {
            "target_version": target, "requirements": None, "checks": checks,
            "findings": [asdict(f) for f in findings], "manual_review": [],
            "summary": {"critical": 1, "warning": 0, "info": 0, "compatible": False},
        }

    current_release = identity.get("moodle_version", {}).get("release")
    upgrade_cmp = _cmp(current_release, req["upgrade_min"])
    if upgrade_cmp is None:
        checks.append(_check("upgrade_path", "unknown", f">= {req['upgrade_min']}", current_release, "Current Moodle release could not be parsed."))
        findings.append(Finding("critical", "CURRENT_MOODLE_VERSION_UNKNOWN", "Current Moodle release is required to prove the upgrade path."))
    elif upgrade_cmp < 0:
        checks.append(_check("upgrade_path", "fail", f">= {req['upgrade_min']}", current_release, "Current Moodle is below the minimum source version for the target."))
        findings.append(Finding("critical", "UPGRADE_PATH_UNSUPPORTED", f"Moodle {target_branch} requires source Moodle {req['upgrade_min']} or later; found {current_release}."))
    else:
        checks.append(_check("upgrade_path", "pass", f">= {req['upgrade_min']}", current_release, "Upgrade source version satisfies the target branch requirement."))

    php_line = platform.get("php", {}).get("version_line")
    php_version = _version_from_line(php_line)
    php_min_cmp = _cmp(php_version, req["php_min"])
    if php_min_cmp is None:
        checks.append(_check("target_php_min", "unknown", f">= {req['php_min']}", php_version, "PHP version could not be parsed."))
        findings.append(Finding("critical", "PHP_VERSION_UNKNOWN", "PHP version is required to prove target compatibility."))
    elif php_min_cmp < 0:
        checks.append(_check("target_php_min", "fail", f">= {req['php_min']}", php_version, "PHP is below the target minimum."))
        findings.append(Finding("critical", "TARGET_PHP_TOO_OLD", f"Moodle {target_branch} requires PHP {req['php_min']} or later; found {php_version}."))
    else:
        checks.append(_check("target_php_min", "pass", f">= {req['php_min']}", php_version, "PHP satisfies the target minimum."))

    if php_version and req.get("php_max") and _cmp(_branch(php_version), req["php_max"]) == 1:
        checks.append(_check("target_php_max", "fail", f"<= {req['php_max']}.x", php_version, "PHP is newer than the maintained maximum for the target branch."))
        findings.append(Finding("critical", "TARGET_PHP_TOO_NEW", f"Moodle {target_branch} is not proven compatible with PHP {php_version}."))
    elif php_version:
        checks.append(_check("target_php_max", "pass", f"<= {req['php_max']}.x", php_version, "PHP is not above the maintained branch maximum."))

    source_branch = _branch(current_release)
    source_req = REQUIREMENTS.get(source_branch or "")
    if source_req and php_version and _cmp(php_version, source_req["php_min"]) == -1:
        findings.append(Finding("critical", "SOURCE_PHP_TOO_OLD", f"Current Moodle {source_branch} itself requires PHP {source_req['php_min']} or later; found {php_version}."))

    modules = {str(module).lower() for module in platform.get("php", {}).get("modules", [])}
    required_extensions = set(BASE_REQUIRED_EXTENSIONS) | set(req.get("required_extensions", set()))
    driver = _normalise_driver(platform.get("database", {}).get("driver"))
    if driver in DB_EXTENSION:
        required_extensions.add(DB_EXTENSION[driver])
    missing_required = sorted(ext for ext in required_extensions if ext.lower() not in modules)
    if modules:
        if missing_required:
            checks.append(_check("php_extensions", "fail", sorted(required_extensions), sorted(modules), "Required PHP extensions are missing."))
            findings.append(Finding("critical", "PHP_EXTENSIONS_MISSING", "Missing required PHP extensions: " + ", ".join(missing_required)))
        else:
            checks.append(_check("php_extensions", "pass", sorted(required_extensions), sorted(modules), "Required PHP extensions are loaded."))
        missing_recommended = sorted(ext for ext in req.get("recommended_extensions", set()) if ext.lower() not in modules)
        if missing_recommended:
            findings.append(Finding("warning", "PHP_EXTENSIONS_RECOMMENDED", "Recommended PHP extensions not loaded: " + ", ".join(missing_recommended)))
    else:
        checks.append(_check("php_extensions", "unknown", sorted(required_extensions), [], "PHP module inventory is empty."))
        findings.append(Finding("critical", "PHP_EXTENSIONS_UNKNOWN", "Loaded PHP extensions are required to prove compatibility."))

    php_settings = platform.get("php", {}).get("settings", {}) or {}
    max_input_vars = php_settings.get("max_input_vars")
    requirement = req.get("max_input_vars")
    if requirement:
        required_now = not req.get("max_input_vars_required_for_php8") or (_numbers(php_version) or (0,))[0] >= 8
        if max_input_vars is None:
            findings.append(Finding("warning" if not required_now else "critical", "MAX_INPUT_VARS_UNKNOWN", f"max_input_vars should be verified against {requirement}."))
        else:
            try:
                actual_miv = int(str(max_input_vars))
            except ValueError:
                actual_miv = None
            if actual_miv is None or actual_miv < requirement:
                severity = "critical" if required_now else "warning"
                findings.append(Finding(severity, "MAX_INPUT_VARS_TOO_LOW", f"max_input_vars must{' ' if required_now else ' preferably '}be >= {requirement}; found {max_input_vars}."))
            else:
                checks.append(_check("max_input_vars", "pass", f">= {requirement}", actual_miv, "PHP setting satisfies the target requirement."))

    if req.get("requires_64bit"):
        int_size = php_settings.get("int_size")
        if int_size is None:
            findings.append(Finding("critical", "PHP_64BIT_UNKNOWN", "Target requires 64-bit PHP; PHP_INT_SIZE was not captured."))
        elif int(int_size) < 8:
            findings.append(Finding("critical", "PHP_64BIT_REQUIRED", f"Moodle {target_branch} requires 64-bit PHP."))

    database = platform.get("database", {})
    db_version = _version_from_line(database.get("version_line") or database.get("image"))
    if not driver:
        findings.append(Finding("critical", "DATABASE_DRIVER_UNKNOWN", "Database driver is required to prove compatibility."))
    elif driver not in req["db_min"]:
        findings.append(Finding("critical", "DATABASE_DRIVER_UNSUPPORTED", f"Database driver {driver} is not supported by Moodle {target_branch}."))
    else:
        minimum = req["db_min"][driver]
        db_cmp = _cmp(db_version, minimum)
        if db_cmp is None:
            findings.append(Finding("critical", "DATABASE_VERSION_UNKNOWN", f"Database version for {driver} could not be proven."))
            checks.append(_check("database_version", "unknown", f">= {minimum}", db_version, "Database version could not be parsed."))
        elif db_cmp < 0:
            findings.append(Finding("critical", "DATABASE_VERSION_TOO_OLD", f"Moodle {target_branch} requires {driver} {minimum} or later; found {db_version}."))
            checks.append(_check("database_version", "fail", f">= {minimum}", db_version, "Database version is below the target minimum."))
        else:
            checks.append(_check("database_version", "pass", f">= {minimum}", db_version, "Database satisfies the target minimum."))

    max_prefix = req.get("max_db_prefix")
    if max_prefix:
        prefix = database.get("prefix")
        if prefix is None:
            findings.append(Finding("critical", "DATABASE_PREFIX_UNKNOWN", f"Moodle {target_branch} requires a database prefix of at most {max_prefix} characters; configure database.prefix so it can be proven."))
        elif len(str(prefix)) > int(max_prefix):
            findings.append(Finding("critical", "DATABASE_PREFIX_TOO_LONG", f"Moodle {target_branch} allows a database prefix of at most {max_prefix} characters; found {prefix!r}."))
        else:
            checks.append(_check("database_prefix", "pass", f"length <= {max_prefix}", prefix, "Database prefix length satisfies the target requirement."))

    manual_review: list[dict[str, Any]] = []
    for plugin in inventory.get("plugins", []):
        classification = plugin.get("classification", "unclassified")
        if classification in {"custom", "unclassified"}:
            manual_review.append({
                "type": "plugin", "path": plugin.get("component_path"), "classification": classification,
                "reason": "Requires target-specific plugin/core comparison.",
            })
    for item in inventory.get("custom_code", {}).get("configured_paths", []):
        if not item.get("exists"):
            findings.append(Finding("critical", "CUSTOM_CODE_UNAVAILABLE", f"Configured custom code could not be inventoried: {item.get('path')}"))
        else:
            manual_review.append({
                "type": "custom_code", "path": item.get("path"), "resolved_path": item.get("resolved_path"),
                "scope": item.get("scope"), "reason": "Requires source compatibility scan.",
            })

    if req.get("public_webroot"):
        findings.append(Finding("warning", "PUBLIC_WEBROOT_MIGRATION_REQUIRED", f"Moodle {target_branch} uses the /public web root layout; deployment/document-root migration must be planned."))

    critical = sum(1 for f in findings if f.severity == "critical")
    warning = sum(1 for f in findings if f.severity == "warning")
    info = sum(1 for f in findings if f.severity == "info")
    return {
        "target_version": target,
        "target_branch": target_branch,
        "current_version": current_release,
        "requirements": _serialise_requirements(req),
        "checks": checks,
        "manual_review": manual_review,
        "findings": [asdict(f) for f in findings],
        "summary": {"critical": critical, "warning": warning, "info": info, "compatible": critical == 0},
    }
