from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import subprocess
from typing import Any, Iterable

DEFAULT_EXTENSIONS = {".php", ".inc", ".sql", ".js", ".mustache"}
DEFAULT_EXCLUDE_DIRS = {".git", "vendor", "node_modules", ".venv", "moodledata"}
PHP_SOURCE_EXTENSIONS = (".php", ".inc")
SQL_AWARE_EXTENSIONS = (".php", ".inc", ".sql")
PHP_CODE_VIEW = "php-code"
DEFAULT_CORE_REFERENCE_MAX_FILES = 100_000
DEFAULT_CORE_COMPONENT_MAX_FILES = 20_000
DEFAULT_CORE_CHANGE_EVIDENCE_LIMIT = 5_000


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    path: str | None = None
    line: int | None = None


@dataclass
class CoreReference:
    repository: Path
    ref: str
    root: str
    commit: str
    object_format: str
    moodle_version: dict[str, str | None]
    manifest: dict[str, str]


class CoreReferenceError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


RISK_PATTERNS: tuple[dict[str, Any], ...] = (
    {
        "id": "php_mysql_extension_removed",
        "severity": "critical",
        "regex": r"\bmysql_(?:query|connect|pconnect|select_db|real_escape_string|fetch_[a-z_]+)\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "source_view": PHP_CODE_VIEW,
        "message": "Legacy mysql_* API is removed from modern PHP.",
    },
    {
        "id": "php_ereg_removed",
        "severity": "critical",
        "regex": r"\b(?:ereg|eregi)\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "source_view": PHP_CODE_VIEW,
        "message": "ereg()/eregi() are removed from modern PHP.",
    },
    {
        "id": "php_split_removed",
        "severity": "critical",
        "regex": r"\b(?:split|spliti)\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "source_view": PHP_CODE_VIEW,
        "message": "split()/spliti() are removed from modern PHP.",
    },
    {
        "id": "php_each_removed",
        "severity": "warning",
        "regex": r"\beach\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "source_view": PHP_CODE_VIEW,
        "message": "each() is incompatible with PHP 8 and should be migrated.",
    },
    {
        "id": "php_create_function_removed",
        "severity": "warning",
        "regex": r"\bcreate_function\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "source_view": PHP_CODE_VIEW,
        "message": "create_function() is incompatible with PHP 8 and should be migrated.",
    },
    {
        "id": "moodle_41_cron_run_single_task_removed",
        "severity": "critical",
        "regex": r"\bcron_run_single_task\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "source_view": PHP_CODE_VIEW,
        "message": "cron_run_single_task() was finally deprecated for Moodle 4.1 and requires migration.",
    },
    {
        "id": "moodle_41_get_module_metadata_removed",
        "severity": "critical",
        "regex": r"\bget_module_metadata\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "source_view": PHP_CODE_VIEW,
        "message": "get_module_metadata() was finally deprecated for Moodle 4.1 and requires migration.",
    },
    {
        "id": "moodle_41_admin_setting_managelicenses_removed",
        "severity": "critical",
        "regex": r"\badmin_setting_managelicenses\b",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "source_view": PHP_CODE_VIEW,
        "message": "admin_setting_managelicenses was finally deprecated for Moodle 4.1 and requires migration.",
    },
    {
        "id": "hardcoded_mdl_prefix",
        "severity": "warning",
        "regex": r"\bmdl_[a-zA-Z0-9_]+\b",
        "min_target": "3.9",
        "extensions": SQL_AWARE_EXTENSIONS,
        "message": "Hard-coded mdl_ table prefix couples code to one database prefix.",
    },
    {
        "id": "legacy_user_contact_column",
        "severity": "warning",
        "regex": r"(?:\bmdl_user\b|\buser\b|\bu\b)\s*\.\s*(?:icq|skype|yahoo|aim|msn)\b|\b(?:icq|skype|yahoo|aim|msn)\b",
        "min_target": "3.11",
        "extensions": SQL_AWARE_EXTENSIONS,
        "message": "Legacy user contact fields were migrated/removed around Moodle 3.11 and require schema review.",
    },
)


def _numbers(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    match = re.search(r"(\d+(?:\.\d+){0,3})", str(value))
    return tuple(int(part) for part in match.group(1).split(".")) if match else ()


def _at_least(value: str | None, minimum: str) -> bool:
    left = _numbers(value)
    right = _numbers(minimum)
    size = max(len(left), len(right))
    return bool(left) and left + (0,) * (size - len(left)) >= right + (0,) * (size - len(right))


def _iter_source_files(root: Path, max_files: int, extensions: set[str], excluded: set[str]) -> Iterable[Path]:
    count = 0
    if root.is_file():
        if root.suffix.lower() in extensions:
            yield root
        return
    for path in root.rglob("*"):
        if any(part in excluded for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        yield path
        count += 1
        if count >= max_files:
            return


def _php_executable_view(text: str) -> str:
    """Mask non-executable PHP regions while preserving line positions.

    PHP files commonly contain inline HTML and JavaScript. Removed-PHP-API
    patterns must inspect only executable PHP code and must not match comments,
    string literals or heredoc/nowdoc contents. The masked view keeps newlines so
    evidence line numbers continue to refer to the original source file.
    """
    masked = [char if char in "\r\n" else " " for char in text]
    state = "inline-html"
    quote = ""
    heredoc_label: str | None = None
    index = 0

    while index < len(text):
        if state == "inline-html":
            if text.startswith("<?=", index):
                state = "code"
                index += 3
                continue
            if text[index:index + 5].lower() == "<?php":
                state = "code"
                index += 5
                continue
            if text.startswith("<?", index) and text[index:index + 5].lower() != "<?xml":
                state = "code"
                index += 2
                continue
            index += 1
            continue

        if state == "code":
            if text.startswith("?>", index):
                state = "inline-html"
                index += 2
                continue
            if text.startswith("//", index):
                state = "line-comment"
                index += 2
                continue
            if text.startswith("/*", index):
                state = "block-comment"
                index += 2
                continue
            if text[index] == "#" and not text.startswith("#[", index):
                state = "line-comment"
                index += 1
                continue
            if text[index] in {"'", '"', "`"}:
                quote = text[index]
                state = "string"
                index += 1
                continue
            if text.startswith("<<<", index):
                match = re.match(r"<<<[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\r\n]*(?:\r\n|\r|\n)", text[index:])
                if match:
                    heredoc_label = match.group(2)
                    state = "heredoc"
                    index += match.end()
                    continue
            masked[index] = text[index]
            index += 1
            continue

        if state == "line-comment":
            if text.startswith("?>", index):
                state = "inline-html"
                index += 2
                continue
            if text[index] in "\r\n":
                state = "code"
            index += 1
            continue

        if state == "block-comment":
            if text.startswith("*/", index):
                state = "code"
                index += 2
                continue
            index += 1
            continue

        if state == "string":
            if text[index] == "\\":
                index += min(2, len(text) - index)
                continue
            if text[index] == quote:
                state = "code"
            index += 1
            continue

        if state == "heredoc":
            line_end = index
            while line_end < len(text) and text[line_end] not in "\r\n":
                line_end += 1
            line = text[index:line_end]
            if heredoc_label and re.fullmatch(rf"[ \t]*{re.escape(heredoc_label)};?[ \t]*", line):
                state = "code"
                heredoc_label = None
            index = line_end
            if index < len(text):
                index += 2 if text.startswith("\r\n", index) else 1

    return "".join(masked)


def _scan_path(root: Path, display_root: Path, target_version: str, max_files: int, max_bytes: int, patterns: tuple[dict[str, Any], ...]) -> tuple[list[dict], dict]:
    hits: list[dict[str, Any]] = []
    scanned_files = 0
    truncated_files = 0
    for file_path in _iter_source_files(root, max_files, DEFAULT_EXTENSIONS, DEFAULT_EXCLUDE_DIRS):
        scanned_files += 1
        try:
            raw = file_path.read_bytes()
        except OSError:
            continue
        if len(raw) > max_bytes:
            raw = raw[:max_bytes]
            truncated_files += 1
        text = raw.decode("utf-8", errors="ignore")
        rel = str(file_path.relative_to(display_root)) if file_path.is_relative_to(display_root) else str(file_path)
        suffix = file_path.suffix.lower()
        source_lines = text.splitlines()
        php_code_lines = _php_executable_view(text).splitlines() if suffix in PHP_SOURCE_EXTENSIONS else []
        for lineno, line in enumerate(source_lines, start=1):
            for pattern in patterns:
                if not _at_least(target_version, pattern["min_target"]):
                    continue
                allowed_extensions = pattern.get("extensions")
                if allowed_extensions and suffix not in allowed_extensions:
                    continue
                candidate_line = line
                if pattern.get("source_view") == PHP_CODE_VIEW:
                    candidate_line = php_code_lines[lineno - 1] if lineno <= len(php_code_lines) else ""
                if re.search(pattern["regex"], candidate_line, flags=re.IGNORECASE):
                    hits.append({"id": pattern["id"], "severity": pattern["severity"], "path": rel, "line": lineno, "message": pattern["message"]})
    return hits, {"scanned_files": scanned_files, "truncated_files": truncated_files, "max_files": max_files, "max_bytes_per_file": max_bytes}


def _valid_git_ref(value: str) -> bool:
    if not value or value.startswith("-") or value.endswith(("/", ".")):
        return False
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", value):
        return False
    return not any(fragment in value for fragment in ("..", "//", "@{"))


def _normalize_tree_root(value: str | None) -> str:
    raw = str(value or ".").strip().replace("\\", "/")
    if raw in {"", "."}:
        return ""
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise CoreReferenceError("CORE_REFERENCE_INVALID", "Core reference root must be a relative Git tree path without traversal.")
    return path.as_posix().rstrip("/")


def _valid_component_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _reference_path(root: str, relative: str) -> str:
    return f"{root}/{relative}" if root else relative


def _git_reference_command(repository: Path, args: list[str], *, binary: bool = False, timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *args],
            capture_output=True,
            text=not binary,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CoreReferenceError("CORE_REFERENCE_UNAVAILABLE", f"Could not inspect configured core reference: {exc.__class__.__name__}.") from exc


def _parse_moodle_version_text(text: str) -> dict[str, str | None]:
    patterns = {
        "release": r"\$release\s*=\s*['\"]([^'\"]+)['\"]",
        "version": r"\$version\s*=\s*([0-9.]+)",
        "branch": r"\$branch\s*=\s*['\"]([^'\"]+)['\"]",
    }
    return {
        key: match.group(1).strip() if (match := re.search(pattern, text)) else None
        for key, pattern in patterns.items()
    }


def _git_tree_manifest(repository: Path, commit: str, root: str, max_files: int) -> dict[str, str]:
    args = ["ls-tree", "-r", "-z", "--full-tree", commit]
    if root:
        args.extend(["--", root])
    proc = _git_reference_command(repository, args, binary=True)
    if proc.returncode != 0:
        raise CoreReferenceError("CORE_REFERENCE_UNAVAILABLE", "Could not list files from configured core reference.")

    prefix = f"{root}/" if root else ""
    manifest: dict[str, str] = {}
    for raw_entry in proc.stdout.split(b"\0"):
        if not raw_entry:
            continue
        metadata, separator, raw_path = raw_entry.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) < 3 or fields[1] != b"blob":
            continue
        path = raw_path.decode("utf-8", errors="surrogateescape")
        if prefix and not path.startswith(prefix):
            continue
        relative = path[len(prefix):] if prefix else path
        manifest[relative] = fields[2].decode("ascii")
        if len(manifest) > max_files:
            raise CoreReferenceError(
                "CORE_REFERENCE_LIMIT_EXCEEDED",
                f"Configured core reference exceeds the {max_files} file comparison limit.",
            )
    return manifest


def _core_reference_settings(cfg: dict[str, Any], inventory: dict[str, Any], moodle_root: Path) -> dict[str, Any] | None:
    structured = cfg.get("core_reference")
    legacy_ref = cfg.get("core_reference_ref")
    repo_root_text = inventory.get("platform", {}).get("git", {}).get("repo_root")

    if structured is not None:
        if not isinstance(structured, dict):
            raise CoreReferenceError("CORE_REFERENCE_INVALID", "plugins.core_reference must be a mapping.")
        repository_text = structured.get("repository") or repo_root_text
        return {
            "repository": repository_text,
            "ref": structured.get("ref"),
            "root": structured.get("root", "."),
            "max_files": int(structured.get("max_files", DEFAULT_CORE_REFERENCE_MAX_FILES)),
            "max_files_per_component": int(structured.get("max_files_per_component", DEFAULT_CORE_COMPONENT_MAX_FILES)),
            "max_changed_files": int(structured.get("max_changed_files", DEFAULT_CORE_CHANGE_EVIDENCE_LIMIT)),
            "legacy": False,
        }

    if not legacy_ref:
        return None
    if not repo_root_text:
        raise CoreReferenceError("CORE_REFERENCE_UNAVAILABLE", "Inventory does not contain the project Git root required by plugins.core_reference_ref.")
    try:
        tree_root = moodle_root.relative_to(Path(repo_root_text).expanduser().resolve()).as_posix()
    except ValueError as exc:
        raise CoreReferenceError("CORE_REFERENCE_INVALID", "Moodle root is outside the inventory Git repository.") from exc
    return {
        "repository": repo_root_text,
        "ref": legacy_ref,
        "root": tree_root,
        "max_files": DEFAULT_CORE_REFERENCE_MAX_FILES,
        "max_files_per_component": DEFAULT_CORE_COMPONENT_MAX_FILES,
        "max_changed_files": DEFAULT_CORE_CHANGE_EVIDENCE_LIMIT,
        "legacy": True,
    }


def _prepare_core_reference(
    cfg: dict[str, Any], inventory: dict[str, Any], moodle_root: Path,
) -> tuple[CoreReference | None, dict[str, Any] | None, Finding | None, dict[str, Any] | None]:
    try:
        settings = _core_reference_settings(cfg, inventory, moodle_root)
    except (CoreReferenceError, TypeError, ValueError) as exc:
        error = exc if isinstance(exc, CoreReferenceError) else CoreReferenceError("CORE_REFERENCE_INVALID", "Core reference limits must be positive integers.")
        return None, {"configured": True, "verified": False, "status": "invalid"}, Finding("warning", error.code, str(error)), None
    if settings is None:
        return None, None, None, None

    evidence: dict[str, Any] = {
        "configured": True,
        "verified": False,
        "status": "unavailable",
        "repository": str(settings.get("repository") or ""),
        "ref": str(settings.get("ref") or ""),
        "root": str(settings.get("root") or "."),
    }
    try:
        repository_text = settings.get("repository")
        ref = str(settings.get("ref") or "")
        if not repository_text or not Path(str(repository_text)).expanduser().is_absolute():
            raise CoreReferenceError("CORE_REFERENCE_INVALID", "Core reference repository must be an absolute local path.")
        if not _valid_git_ref(ref):
            raise CoreReferenceError("CORE_REFERENCE_INVALID", "Core reference ref contains unsupported or unsafe characters.")
        root = _normalize_tree_root(str(settings.get("root") or "."))
        for limit_name in ("max_files", "max_files_per_component", "max_changed_files"):
            if int(settings[limit_name]) <= 0:
                raise CoreReferenceError("CORE_REFERENCE_INVALID", f"Core reference {limit_name} must be positive.")

        repository = Path(str(repository_text)).expanduser().resolve()
        revision = _git_reference_command(repository, ["rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"])
        if revision.returncode != 0:
            raise CoreReferenceError("CORE_REFERENCE_UNAVAILABLE", "Configured core reference ref cannot be resolved locally.")
        commit = revision.stdout.strip()
        version_path = _reference_path(root, "version.php")
        version_proc = _git_reference_command(repository, ["cat-file", "blob", f"{commit}:{version_path}"], binary=True)
        if version_proc.returncode != 0:
            raise CoreReferenceError("CORE_REFERENCE_UNAVAILABLE", "Configured core reference does not contain Moodle version.php at its configured root.")
        reference_version = _parse_moodle_version_text(version_proc.stdout.decode("utf-8", errors="ignore"))
        inventory_version = inventory.get("identity", {}).get("moodle_version", {}) or {}
        evidence["reference_moodle_version"] = reference_version
        evidence["inventory_moodle_version"] = {
            key: inventory_version.get(key) for key in ("release", "version", "branch")
        }
        comparable_keys = ("release", "version", "branch")
        if not all(inventory_version.get(key) for key in comparable_keys):
            raise CoreReferenceError("CORE_REFERENCE_VERSION_UNKNOWN", "Inventory does not contain enough Moodle version data to verify the core reference.")
        mismatched = [key for key in comparable_keys if str(reference_version.get(key) or "") != str(inventory_version.get(key) or "")]
        if mismatched:
            raise CoreReferenceError(
                "CORE_REFERENCE_VERSION_MISMATCH",
                f"Configured core reference does not exactly match inventory Moodle version fields: {', '.join(mismatched)}.",
            )
        object_format_proc = _git_reference_command(repository, ["rev-parse", "--show-object-format"])
        object_format = object_format_proc.stdout.strip() if object_format_proc.returncode == 0 else "sha1"
        if object_format not in hashlib.algorithms_available:
            raise CoreReferenceError("CORE_REFERENCE_UNAVAILABLE", f"Unsupported Git object format: {object_format}.")
        manifest = _git_tree_manifest(repository, commit, root, int(settings["max_files"]))
        if not manifest:
            raise CoreReferenceError("CORE_REFERENCE_UNAVAILABLE", "Configured core reference tree is empty.")
    except CoreReferenceError as exc:
        evidence["status"] = {
            "CORE_REFERENCE_INVALID": "invalid",
            "CORE_REFERENCE_VERSION_MISMATCH": "version-mismatch",
            "CORE_REFERENCE_VERSION_UNKNOWN": "version-unknown",
            "CORE_REFERENCE_LIMIT_EXCEEDED": "limit-exceeded",
        }.get(exc.code, "unavailable")
        return None, evidence, Finding("warning", exc.code, str(exc)), settings

    reference = CoreReference(repository, ref, root, commit, object_format, reference_version, manifest)
    evidence.update({
        "verified": True,
        "status": "verified",
        "repository": str(repository),
        "ref": ref,
        "root": root or ".",
        "commit": commit,
        "moodle_version": reference_version,
        "file_count": len(manifest),
    })
    return reference, evidence, None, settings


def _git_blob_oid(path: Path, object_format: str) -> str | None:
    try:
        if path.is_symlink():
            data = os.readlink(path).encode("utf-8", errors="surrogateescape")
        elif path.is_file():
            data = path.read_bytes()
        else:
            return None
    except OSError:
        return None
    digest = hashlib.new(object_format)
    digest.update(f"blob {len(data)}\0".encode("ascii"))
    digest.update(data)
    return digest.hexdigest()


def _local_component_manifest(root: Path, component_path: str, object_format: str, max_files: int) -> dict[str, str] | None:
    component_root = root.joinpath(*PurePosixPath(component_path).parts)
    if not component_root.is_dir():
        return {}
    manifest: dict[str, str] = {}
    for path in sorted(component_root.rglob("*")):
        if not (path.is_file() or path.is_symlink()):
            continue
        relative = path.relative_to(root).as_posix()
        oid = _git_blob_oid(path, object_format)
        if oid is None:
            return None
        manifest[relative] = oid
        if len(manifest) > max_files:
            return None
    return manifest


def _compare_component(
    reference: CoreReference, moodle_root: Path, component_path: str, max_files: int, max_changed_files: int,
) -> dict[str, Any]:
    if not _valid_component_path(component_path):
        return {"status": "unavailable", "reason": "Component path is not a safe relative path."}
    prefix = f"{component_path.rstrip('/')}/"
    reference_manifest = {path: oid for path, oid in reference.manifest.items() if path.startswith(prefix)}
    if not reference_manifest:
        return {"status": "absent", "changed_file_count": 0, "changed_files": []}
    local_manifest = _local_component_manifest(moodle_root, component_path, reference.object_format, max_files)
    if local_manifest is None:
        return {"status": "unavailable", "reason": "Local component comparison limit exceeded or a file could not be read."}
    changed = sorted(path for path in set(reference_manifest) | set(local_manifest) if reference_manifest.get(path) != local_manifest.get(path))
    return {
        "status": "exact-match" if not changed else "modified",
        "changed_file_count": len(changed),
        "changed_files": changed[:max_changed_files],
        "changed_files_truncated": len(changed) > max_changed_files,
    }


def _compare_core_files(reference: CoreReference, moodle_root: Path, max_changed_files: int) -> tuple[list[str], int]:
    changed: list[str] = []
    count = 0
    for relative, expected_oid in reference.manifest.items():
        actual_oid = _git_blob_oid(moodle_root.joinpath(*PurePosixPath(relative).parts), reference.object_format)
        if actual_oid == expected_oid:
            continue
        count += 1
        if len(changed) < max_changed_files:
            changed.append(relative)
    return changed, count


def _scan_path_covers(parent: Path, child: Path) -> bool:
    if parent == child:
        return True
    if not parent.is_dir():
        return False
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _deduplicate_scan_targets(scan_targets: list[tuple[str, Path]]) -> tuple[list[tuple[str, Path]], list[dict[str, str]]]:
    """Return minimal non-overlapping scan roots plus evidence for covered paths.

    Parents are considered before descendants regardless of configuration order, so
    configuring both ../batch and ../batch/edx never scans the edx tree twice.
    """
    normalized = [(index, label, path.resolve()) for index, (label, path) in enumerate(scan_targets)]
    ordered = sorted(normalized, key=lambda item: (len(item[2].parts), item[0]))
    selected: list[tuple[int, str, Path]] = []
    covered: list[tuple[int, dict[str, str]]] = []

    for index, label, resolved in ordered:
        covering = next(
            ((selected_label, selected_path) for _, selected_label, selected_path in selected if _scan_path_covers(selected_path, resolved)),
            None,
        )
        if covering:
            covering_label, covering_path = covering
            covered.append((index, {
                "path": label,
                "resolved_path": str(resolved),
                "covered_by": covering_label,
                "covered_by_resolved_path": str(covering_path),
            }))
            continue
        selected.append((index, label, resolved))

    selected.sort(key=lambda item: item[0])
    covered.sort(key=lambda item: item[0])
    return [(label, path) for _, label, path in selected], [item for _, item in covered]


def analyze_plugins(config: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    target = config.get("moodle", {}).get("target_version") or inventory.get("identity", {}).get("target_version")
    root = Path(config["moodle"]["root"]).expanduser().resolve()
    findings: list[Finding] = []
    plugins: list[dict[str, Any]] = [dict(plugin) for plugin in inventory.get("plugins", [])]
    review: list[dict[str, Any]] = []
    cfg = config.get("plugins", {})
    compatibility_map = cfg.get("compatibility", {}) or {}
    ignore = set(cfg.get("ignore", []) or [])

    reference, reference_evidence, reference_finding, reference_settings = _prepare_core_reference(cfg, inventory, root)
    if reference_finding:
        findings.append(reference_finding)

    if reference and reference_settings:
        component_limit = int(reference_settings["max_files_per_component"])
        changed_limit = int(reference_settings["max_changed_files"])
        for item in plugins:
            path = item.get("component_path")
            if not path:
                continue
            comparison = _compare_component(reference, root, str(path), component_limit, changed_limit)
            item["core_reference_comparison"] = comparison
            status = comparison["status"]
            if item.get("classification") == "custom":
                continue
            if status == "exact-match":
                item["classification"] = "core"
                item["classification_reason"] = "exact content match with verified source-core reference"
            elif status == "modified":
                item["classification"] = "core-modified"
                item["classification_reason"] = "component exists in verified source core but local content differs"
            elif status == "absent":
                item["classification"] = "non-core"
                item["classification_reason"] = "component is absent from verified source-core reference"
            else:
                item["classification"] = "unclassified"
                item["classification_reason"] = "component comparison with verified source core was unavailable"
                findings.append(Finding(
                    "warning",
                    "CORE_COMPONENT_COMPARE_UNAVAILABLE",
                    "Could not complete bounded comparison for plugin component.",
                    str(path),
                ))

    for item in plugins:
        path = item.get("component_path")
        if not path or path in ignore:
            item["review_status"] = "ignored"
            continue
        declared = compatibility_map.get(path, [])
        if isinstance(declared, str):
            declared = [declared]
        branch = ".".join(str(target).split(".")[:2]) if target else None
        classification = item.get("classification")
        comparison_status = item.get("core_reference_comparison", {}).get("status")
        if classification == "core" and comparison_status == "exact-match":
            item["review_status"] = "core-reference-match"
        elif declared and branch in {str(value) for value in declared}:
            item["review_status"] = "declared-compatible"
        elif classification in {"custom", "core-modified", "non-core"}:
            item["review_status"] = "scan-required"
            reasons = {
                "custom": "Custom plugin has no declared target compatibility.",
                "core-modified": "Modified source-core component requires target compatibility review.",
                "non-core": "Non-core plugin has no declared target compatibility.",
            }
            review.append({"type": "plugin", "path": path, "reason": reasons[str(classification)]})
        else:
            item["review_status"] = "core-comparison-required"
            review.append({"type": "plugin", "path": path, "reason": "Plugin remains unclassified until compared with exact Moodle core."})

    scan_cfg = config.get("custom_code", {}) or {}
    max_files = int(scan_cfg.get("scan_max_files_per_path", 20_000))
    max_bytes = int(scan_cfg.get("scan_max_bytes_per_file", 1_000_000))
    scan_targets: list[tuple[str, Path]] = []
    for item in inventory.get("custom_code", {}).get("configured_paths", []):
        if not item.get("exists"):
            findings.append(Finding("critical", "CUSTOM_PATH_UNAVAILABLE", f"Cannot scan configured custom path: {item.get('path')}", item.get("path")))
            continue
        resolved = item.get("resolved_path")
        if resolved:
            scan_targets.append((item.get("path") or resolved, Path(resolved)))
    for plugin in plugins:
        if plugin.get("classification") not in {"custom", "core-modified", "non-core"} or plugin.get("review_status") == "ignored":
            continue
        path = plugin.get("component_path")
        if not _valid_component_path(str(path)):
            findings.append(Finding("critical", "PLUGIN_PATH_INVALID", "Plugin component path is not a safe relative path.", str(path)))
            continue
        candidate = (root / str(path)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            findings.append(Finding("critical", "PLUGIN_PATH_INVALID", "Plugin component path resolves outside Moodle root.", str(path)))
            continue
        if candidate.exists():
            scan_targets.append((str(path), candidate))

    scan_targets, covered_scan_paths = _deduplicate_scan_targets(scan_targets)

    all_hits: list[dict[str, Any]] = []
    scan_summaries: list[dict[str, Any]] = []
    for label, resolved in scan_targets:
        hits, summary = _scan_path(resolved, resolved if resolved.is_dir() else resolved.parent, str(target), max_files, max_bytes, RISK_PATTERNS)
        for hit in hits:
            hit["scope"] = label
        all_hits.extend(hits)
        scan_summaries.append({"path": label, "resolved_path": str(resolved), **summary, "hits": len(hits)})
    for hit in all_hits:
        findings.append(Finding(hit["severity"], f"CODE_{hit['id'].upper()}", hit["message"], hit["path"], hit["line"]))

    core_modifications: list[str] | None = None
    core_modification_count: int | None = None
    core_modifications_truncated = False
    core_ref = reference_evidence.get("ref") if reference_evidence else cfg.get("core_reference_ref")
    if reference and reference_settings:
        core_modifications, core_modification_count = _compare_core_files(reference, root, int(reference_settings["max_changed_files"]))
        core_modifications_truncated = core_modification_count > len(core_modifications)
        if core_modification_count:
            findings.append(Finding(
                "warning",
                "CORE_DIFF_PRESENT",
                f"Verified source-core comparison found {core_modification_count} modified or missing core files.",
            ))

    counts = Counter(f.severity for f in findings)
    classifications = Counter(str(plugin.get("classification") or "unclassified") for plugin in plugins)
    return {
        "target_version": target, "plugins": plugins, "custom_code_scans": scan_summaries, "covered_scan_paths": covered_scan_paths, "risk_hits": all_hits,
        "core_reference_ref": core_ref, "core_reference": reference_evidence,
        "core_modifications": core_modifications, "core_modification_count": core_modification_count,
        "core_modifications_truncated": core_modifications_truncated, "manual_review": review,
        "findings": [asdict(f) for f in findings],
        "summary": {
            "critical": counts["critical"], "warning": counts["warning"], "info": counts["info"],
            "plugin_count": len(plugins), "risk_hit_count": len(all_hits), "review_count": len(review),
            "scan_root_count": len(scan_summaries), "covered_scan_path_count": len(covered_scan_paths),
            "classification_counts": dict(sorted(classifications.items())), "ready": counts["critical"] == 0,
        },
    }
