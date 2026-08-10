from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable


@dataclass
class Finding:
    severity: str
    code: str
    message: str


MUTATION_RE = re.compile(
    r"\b(insert|update|delete|replace|alter|drop|create|truncate|grant|revoke|call|set|load|outfile|dumpfile|lock|unlock|rename)\b",
    re.IGNORECASE,
)
ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def _strip_sql_literals_comments(sql: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    text = re.sub(r"--[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    text = re.sub(r"'(?:''|\\.|[^'])*'", "''", text)
    text = re.sub(r'"(?:""|\\.|[^"])*"', '""', text)
    return text


def is_read_only_sql(sql: str) -> bool:
    cleaned = _strip_sql_literals_comments(sql).strip()
    if not cleaned:
        return False
    statements = [part.strip() for part in cleaned.split(";") if part.strip()]
    if len(statements) != 1:
        return False
    first = statements[0].split(None, 1)[0].upper()
    if first not in {"SELECT", "SHOW", "EXPLAIN", "DESCRIBE", "DESC", "WITH"}:
        return False
    return MUTATION_RE.search(statements[0]) is None


def _env_value(mapping: dict[str, str], key: str, required: bool = True) -> str | None:
    env_name = mapping.get(key)
    if not env_name:
        if required:
            raise ValueError(f"database.connection_env.{key} is not configured")
        return None
    value = os.environ.get(env_name)
    if value is None and required:
        raise ValueError(f"Required database environment variable is not set: {env_name}")
    return value


def _container_env_name(mapping: dict[str, str], key: str, required: bool = True) -> str | None:
    name = mapping.get(key)
    if not name:
        if required:
            raise ValueError(f"database.container_connection_env.{key} is not configured")
        return None
    if not ENV_NAME_RE.fullmatch(str(name)):
        raise ValueError(f"database.container_connection_env.{key} is not an argv-safe environment variable name")
    return str(name)


def _build_container_env_command(db: dict[str, Any], driver: str, container: str) -> tuple[list[str], dict[str, str], str]:
    mapping = db.get("container_connection_env", {}) or {}
    database_env = _container_env_name(mapping, "database")
    user_env = _container_env_name(mapping, "user")
    password_env = _container_env_name(mapping, "password", required=False) or "MUK_UNSET_DATABASE_PASSWORD"
    host = str(db.get("container_host", "127.0.0.1"))
    default_port = 3306 if driver in {"mysql", "mariadb"} else 5432
    port = str(db.get("container_port", default_port))
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", host) or not port.isdigit() or not 0 < int(port) <= 65535:
        raise ValueError("database container_host/container_port is invalid")

    resolve_env = (
        'eval "database_value=\\${$1-}"\n'
        'eval "user_value=\\${$2-}"\n'
        'eval "password_value=\\${$3-}"\n'
        'if [ -z "$database_value" ] || [ -z "$user_value" ]; then '\
        'echo "Required database container environment is unavailable" >&2; exit 64; fi\n'
    )
    if driver in {"mysql", "mariadb"}:
        script = resolve_env + 'exec env MYSQL_PWD="$password_value" mysql --batch --raw -h "$4" -P "$5" -u "$user_value" "$database_value"'
    elif driver == "pgsql":
        script = resolve_env + 'exec env PGPASSWORD="$password_value" psql -A -F "\t" -P footer=off -h "$4" -p "$5" -U "$user_value" -d "$database_value"'
    else:
        raise ValueError(f"Unsupported database validation driver: {driver}")
    command = [
        "docker", "exec", "-i", container, "sh", "-c", script, "muk-database",
        database_env, user_env, password_env, host, port,
    ]
    return command, os.environ.copy(), f"docker-env:{container}"


def _build_command(config: dict[str, Any]) -> tuple[list[str], dict[str, str], str]:
    db = config.get("database", {})
    driver = {"postgres": "pgsql", "postgresql": "pgsql"}.get(str(db.get("driver", "")).lower(), str(db.get("driver", "")).lower())
    container = db.get("runtime_container")
    if db.get("container_connection_env") is not None:
        if not container:
            raise ValueError("database.runtime_container is required with container_connection_env")
        return _build_container_env_command(db, driver, str(container))
    mapping = db.get("connection_env", {}) or {}
    host = _env_value(mapping, "host")
    database = _env_value(mapping, "database")
    user = _env_value(mapping, "user")
    port = _env_value(mapping, "port", required=False)
    password = _env_value(mapping, "password", required=False)
    env = os.environ.copy()
    if driver in {"mysql", "mariadb"}:
        if password is not None:
            env["MYSQL_PWD"] = password
        client = ["mysql", "--batch", "--raw", "-h", str(host), "-u", str(user), str(database)]
        if port:
            client.extend(["-P", str(port)])
        secret_env = "MYSQL_PWD"
    elif driver == "pgsql":
        if password is not None:
            env["PGPASSWORD"] = password
        client = ["psql", "-A", "-F", "\t", "-P", "footer=off", "-h", str(host), "-U", str(user), "-d", str(database)]
        if port:
            client.extend(["-p", str(port)])
        secret_env = "PGPASSWORD"
    else:
        raise ValueError(f"Unsupported database validation driver: {driver}")
    if container:
        client = ["docker", "exec", "-i", "-e", secret_env, str(container), *client]
        mode = f"docker:{container}"
    else:
        mode = "local"
    return client, env, mode


def _run_process(command: list[str], sql: str, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, input=sql, capture_output=True, text=True, env=env, timeout=timeout, check=False)


def _parse_tsv(stdout: str, max_rows: int) -> tuple[list[dict[str, str]], bool]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return [], False
    header = lines[0].split("\t")
    data = lines[1:]
    rows = []
    for line in data[:max_rows]:
        values = line.split("\t") + [""] * max(0, len(header) - len(line.split("\t")))
        rows.append(dict(zip(header, values[:len(header)])))
    return rows, len(data) > max_rows


def _expectation_ok(expect: str, row_count: int) -> bool:
    if expect == "empty":
        return row_count == 0
    if expect == "nonempty":
        return row_count > 0
    if expect == "any":
        return True
    raise ValueError(f"Unsupported database check expectation: {expect}")


def run_database_checks(config: dict[str, Any], runner: Callable[[list[str], str, dict[str, str], int], Any] | None = None) -> dict[str, Any]:
    db = config.get("database", {})
    checks = db.get("checks", []) or []
    findings: list[Finding] = []
    results: list[dict[str, Any]] = []
    max_sample_rows = int(db.get("max_sample_rows", 20))
    timeout = int(db.get("timeout_seconds", 30))
    runner = runner or _run_process
    if not checks:
        return {"driver": db.get("driver"), "execution_mode": None, "checks": [], "findings": [], "summary": {"critical": 0, "warning": 0, "configured": 0, "executed": 0, "passed": 0, "complete": False}}
    try:
        command, env, mode = _build_command(config)
    except ValueError as exc:
        severity = "critical" if any(str(c.get("severity", "warning")) == "critical" for c in checks) else "warning"
        findings.append(Finding(severity, "DATABASE_CONNECTION_UNAVAILABLE", str(exc)))
        return {"driver": db.get("driver"), "execution_mode": None, "checks": [], "findings": [asdict(f) for f in findings], "summary": {"critical": int(severity == "critical"), "warning": int(severity == "warning"), "configured": len(checks), "executed": 0, "passed": 0, "complete": False}}

    for spec in checks:
        check_id = str(spec.get("id") or spec.get("sql_file") or "unnamed")
        severity = str(spec.get("severity", "warning"))
        sql_file = Path(str(spec.get("sql_file", "")))
        expect = str(spec.get("expect", "empty"))
        item = {"id": check_id, "severity": severity, "sql_file": str(sql_file), "expect": expect, "executed": False, "ok": False, "row_count": None, "sample": [], "sample_truncated": False, "error": None}
        if not sql_file.is_file():
            item["error"] = "SQL file does not exist"
            findings.append(Finding(severity, "DATABASE_CHECK_FILE_MISSING", f"{check_id}: SQL file not found: {sql_file}"))
            results.append(item)
            continue
        sql = sql_file.read_text(encoding="utf-8")
        if not is_read_only_sql(sql):
            item["error"] = "SQL rejected by read-only validation policy"
            findings.append(Finding("critical", "DATABASE_MUTATION_SQL_REJECTED", f"{check_id}: validation SQL is not provably read-only."))
            results.append(item)
            continue
        try:
            proc = runner(command, sql, env, timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
            findings.append(Finding(severity, "DATABASE_CHECK_EXECUTION_FAILED", f"{check_id}: database check could not execute."))
            results.append(item)
            continue
        item["executed"] = True
        if int(proc.returncode) != 0:
            item["error"] = (str(proc.stderr).strip() or "database client returned non-zero")[:1000]
            findings.append(Finding(severity, "DATABASE_CHECK_FAILED", f"{check_id}: database client returned {proc.returncode}."))
            results.append(item)
            continue
        rows, truncated = _parse_tsv(str(proc.stdout), max_sample_rows)
        row_count = max(0, len([line for line in str(proc.stdout).splitlines() if line.strip()]) - 1)
        item.update({"row_count": row_count, "sample": rows, "sample_truncated": truncated})
        try:
            item["ok"] = _expectation_ok(expect, row_count)
        except ValueError as exc:
            item["error"] = str(exc)
            findings.append(Finding("critical", "DATABASE_EXPECTATION_INVALID", f"{check_id}: {exc}"))
            results.append(item)
            continue
        if not item["ok"]:
            findings.append(Finding(severity, "DATABASE_CHECK_EXPECTATION_FAILED", f"{check_id}: expectation {expect!r} failed with {row_count} row(s)."))
        results.append(item)

    critical = sum(1 for f in findings if f.severity == "critical")
    warning = sum(1 for f in findings if f.severity == "warning")
    executed = sum(1 for item in results if item["executed"])
    return {"driver": db.get("driver"), "execution_mode": mode, "checks": results, "findings": [asdict(f) for f in findings], "summary": {"critical": critical, "warning": warning, "configured": len(checks), "executed": executed, "passed": sum(1 for item in results if item["executed"] and item["ok"]), "complete": critical == 0 and executed == len(checks)}}
