from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import shlex
import subprocess
from time import time
from typing import Any, Callable


@dataclass
class Finding:
    severity: str
    code: str
    message: str


SHELL_TOKENS = {"&&", "||", "|", ";", ">", ">>", "<", "<<"}
SECRET_ARG_RE = re.compile(r"(?i)(--?(?:password|passwd|token|secret)(?:=|$)|^-p\S+)")


def command_argv(command: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(command, str):
        argv = shlex.split(command)
    else:
        argv = [str(part) for part in command]
    if not argv:
        raise ValueError("Configured command is empty")
    if any(part in SHELL_TOKENS or "$(" in part or "`" in part for part in argv):
        raise ValueError("Shell control syntax is not allowed; configure an argument-vector command or a dedicated script")
    if any(SECRET_ARG_RE.search(part) for part in argv):
        raise ValueError("Credentials must not be passed in configured command arguments")
    return argv


def _redact(text: str) -> str:
    text = re.sub(r"(?i)\b(password|passwd|token|secret)\s*=\s*\S+", r"\1=[REDACTED]", text)
    return re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", text)


def runtime_argv(config: dict[str, Any], command: str | list[str]) -> tuple[list[str], Path | None]:
    argv = command_argv(command)
    runtime = config.get("runtime", {}) or {}
    if runtime.get("type", "local") == "docker":
        container = runtime.get("container")
        root = runtime.get("moodle_root")
        if not container or not root:
            raise ValueError("Docker runtime requires container and moodle_root")
        return ["docker", "exec", "-w", str(root), str(container), *argv], None
    return argv, Path(config["moodle"]["root"]).expanduser().resolve()


def run_command(
    config: dict[str, Any],
    command: str | list[str],
    runner: Callable[..., Any] | None = None,
    timeout: int = 3600,
    max_output_chars: int = 20_000,
) -> dict[str, Any]:
    argv, cwd = runtime_argv(config, command)
    runner = runner or subprocess.run
    started = time()
    try:
        proc = runner(argv, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "command": argv, "cwd": str(cwd) if cwd else None, "exit_code": int(proc.returncode),
            "ok": int(proc.returncode) == 0, "duration_seconds": round(time() - started, 3),
            "stdout_tail": _redact(str(proc.stdout))[-max_output_chars:], "stderr_tail": _redact(str(proc.stderr))[-max_output_chars:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "command": argv, "cwd": str(cwd) if cwd else None, "exit_code": None, "ok": False,
            "duration_seconds": round(time() - started, 3), "stdout_tail": "", "stderr_tail": _redact(f"{type(exc).__name__}: {exc}"),
        }


def mutation_preconditions(
    config: dict[str, Any],
    approved: bool,
    inventory: dict[str, Any] | None,
    compatibility: dict[str, Any] | None,
    backup: dict[str, Any] | None,
) -> list[dict[str, str]]:
    safety = config.get("safety", {}) or {}
    findings: list[Finding] = []
    if not safety.get("allow_mutation", False):
        findings.append(Finding("critical", "MUTATION_DISABLED", "safety.allow_mutation is false."))
    required_env = safety.get("require_environment")
    actual_env = config.get("project", {}).get("environment")
    if required_env and actual_env != required_env:
        findings.append(Finding("critical", "ENVIRONMENT_NOT_ALLOWED", f"Mutation requires environment {required_env!r}; current environment is {actual_env!r}."))
    if safety.get("require_human_gate", True) and not approved:
        findings.append(Finding("critical", "HUMAN_APPROVAL_REQUIRED", "Explicit human approval was not supplied."))
    if not inventory:
        findings.append(Finding("critical", "INVENTORY_EVIDENCE_REQUIRED", "Inventory evidence is required before mutation."))
    elif safety.get("require_clean_git", True):
        git = inventory.get("platform", {}).get("git", {})
        if not git.get("is_repo"):
            findings.append(Finding("critical", "GIT_STATE_UNKNOWN", "A Git working tree is required by safety policy."))
        elif git.get("dirty") is not False:
            findings.append(Finding("critical", "GIT_NOT_CLEAN", "Git working tree is dirty or its clean state is unknown."))
    if not compatibility or not compatibility.get("summary", {}).get("compatible", False):
        findings.append(Finding("critical", "COMPATIBILITY_NOT_PASSED", "Passing compatibility evidence is required before mutation."))
    if safety.get("require_backup_check", True) and (not backup or not backup.get("summary", {}).get("verified", False)):
        findings.append(Finding("critical", "BACKUP_NOT_VERIFIED", "Verified backup evidence is required before mutation."))
    return [asdict(f) for f in findings]
