from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from .backup import verify_backups
from .agents import orchestrate_agents
from .baseline import capture_baseline
from .compare import compare_endpoint_sets
from .compatibility import assess_compatibility
from .config import ConfigError, load_config
from .database import run_database_checks
from .document import generate_report
from .endpoints import run_endpoint_checks
from .evidence import read_json, run_dir, write_json
from .inventory import collect_inventory
from .logs import analyze_log_sources
from .plugins import analyze_plugins
from .rollback import execute_rollback, render_rollback_plan
from .upgrade import execute_upgrade, render_upgrade_plan
from .validate import validate_upgrade


def _json_print(payload):
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _evidence_path(rd: Path, *names: str) -> Path:
    for name in names:
        path = rd / name
        if path.is_file():
            return path
    raise FileNotFoundError(f"Required evidence missing; expected one of: {', '.join(names)}")


def _read_optional(rd: Path, name: str):
    path = rd / name
    return read_json(path) if path.is_file() else None


def cmd_validate_config(args):
    load_config(args.config)
    print("config: OK")
    return 0


def cmd_new_run(args):
    cfg = load_config(args.config)
    rid = args.run_id or datetime.now(timezone.utc).strftime("UPG-%Y%m%d-%H%M%S")
    rd = run_dir(rid)
    write_json(rd / "metadata.json", {"run_id": rid, "project": cfg["project"], "target_version": cfg["moodle"]["target_version"], "moodle_root": cfg["moodle"]["root"], "base_url": cfg["moodle"]["base_url"]})
    print(rid)
    return 0


def cmd_inventory(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    result = collect_inventory(cfg)
    if args.phase == "before":
        write_json(rd / "inventory-before.json", result)
        write_json(rd / "inventory.json", result)
    else:
        write_json(rd / "inventory-after.json", result)
    _json_print(result)
    return 2 if result.get("summary", {}).get("critical", 0) else 0


def cmd_compatibility(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    inventory = read_json(_evidence_path(rd, "inventory-before.json", "inventory.json"))
    result = assess_compatibility(inventory, cfg["moodle"]["target_version"])
    write_json(rd / "compatibility.json", result)
    _json_print(result)
    return 2 if result.get("summary", {}).get("critical", 0) else 0


def cmd_plugins(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    inventory = read_json(_evidence_path(rd, "inventory-before.json", "inventory.json"))
    result = analyze_plugins(cfg, inventory)
    write_json(rd / "plugins.json", result)
    _json_print(result)
    return 2 if result.get("summary", {}).get("critical", 0) else 0


def cmd_endpoints(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    results = run_endpoint_checks(cfg)
    write_json(rd / f"endpoints-{args.phase}.json", results)
    _json_print(results)
    return 0 if results and all(item.get("executed") and item.get("ok") for item in results) else 2


def cmd_logs(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    logs_cfg = cfg.get("logs", {})
    result = analyze_log_sources(logs_cfg)
    write_json(rd / f"logs-{args.phase}.json", result)
    _json_print(result)
    return 0 if result.get("summary", {}).get("complete", False) else 2


def cmd_database(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    result = run_database_checks(cfg)
    write_json(rd / f"database-{args.phase}.json", result)
    _json_print(result)
    return 0 if result.get("summary", {}).get("complete", False) else 2


def cmd_baseline(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    inventory = read_json(_evidence_path(rd, "inventory-before.json", "inventory.json"))
    result = capture_baseline(cfg, inventory)
    write_json(rd / "endpoints-before.json", result["endpoint_checks"])
    write_json(rd / "logs-before.json", result["log_checks"])
    write_json(rd / "database-before.json", result["database_checks"])
    write_json(rd / "baseline-before.json", result)
    _json_print(result)
    return 2 if not result.get("summary", {}).get("complete", False) else 0


def cmd_backup(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    result = verify_backups(cfg)
    write_json(rd / "backup.json", result)
    _json_print(result)
    return 2 if not result.get("summary", {}).get("verified", False) else 0


def cmd_upgrade(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    inventory = read_json(_evidence_path(rd, "inventory-before.json", "inventory.json"))
    compatibility = read_json(_evidence_path(rd, "compatibility.json"))
    backup = read_json(_evidence_path(rd, "backup.json"))
    baseline = read_json(_evidence_path(rd, "baseline-before.json"))
    plugins = read_json(_evidence_path(rd, "plugins.json"))
    (rd / "upgrade-plan.md").write_text(render_upgrade_plan(cfg), encoding="utf-8")
    result = execute_upgrade(cfg, args.approved, inventory, compatibility, backup, baseline=baseline, plugins=plugins)
    write_json(rd / "upgrade-result.json", result)
    _json_print(result)
    return 0 if result.get("summary", {}).get("completed", False) else 3


def cmd_validate(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    baseline = read_json(_evidence_path(rd, "baseline-before.json"))
    inventory_after = read_json(_evidence_path(rd, "inventory-after.json"))
    endpoints_after = read_json(_evidence_path(rd, "endpoints-after.json"))
    logs_after = read_json(_evidence_path(rd, "logs-after.json"))
    database_after = read_json(_evidence_path(rd, "database-after.json"))
    result = validate_upgrade(cfg, baseline, inventory_after, endpoints_after, logs_after, database_after, mode=args.mode)
    write_json(rd / "validation.json", result)
    _json_print(result)
    return 0 if result.get("summary", {}).get("accepted", False) else 3


def cmd_rollback(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    backup = read_json(_evidence_path(rd, "backup.json"))
    validation = _read_optional(rd, "validation.json")
    (rd / "rollback-plan.md").write_text(render_rollback_plan(cfg), encoding="utf-8")
    result = execute_rollback(cfg, args.approved, backup, validation, force=args.force)
    write_json(rd / "rollback-result.json", result)
    _json_print(result)
    return 0 if result.get("summary", {}).get("restored", False) else 3


def cmd_document(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    markdown, result = generate_report(cfg, args.run_id, base_dir=rd.parent)
    (rd / "final-report.md").write_text(markdown + "\n", encoding="utf-8")
    write_json(rd / "document-result.json", result)
    _json_print(result)
    return 0 if result.get("summary", {}).get("report_generated", False) else 3


def cmd_compare(args):
    result = compare_endpoint_sets(read_json(args.before), read_json(args.after))
    _json_print(result)
    return 0 if result["ok"] else 3


def cmd_orchestrate(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    result = orchestrate_agents(
        cfg,
        rd,
        workflow=args.workflow,
        pre_upgrade_approved=args.pre_upgrade_approved,
        acceptance_approved=args.acceptance_approved,
        rollback_approved=args.rollback_approved,
        force_rollback=args.force_rollback,
        agents_dir=args.agents_dir,
    )
    write_json(rd / "agent-state.json", result)
    _json_print(result)
    return 3 if result.get("status") == "blocked" else 0


def build_parser():
    parser = argparse.ArgumentParser(prog="muk")
    sub = parser.add_subparsers(dest="cmd", required=True)

    command = sub.add_parser("validate-config")
    command.add_argument("--config", required=True)
    command.set_defaults(func=cmd_validate_config)

    command = sub.add_parser("new-run")
    command.add_argument("--config", required=True)
    command.add_argument("--run-id")
    command.set_defaults(func=cmd_new_run)

    command = sub.add_parser("inventory")
    command.add_argument("--config", required=True)
    command.add_argument("--run-id", required=True)
    command.add_argument("--phase", choices=["before", "after"], default="before")
    command.set_defaults(func=cmd_inventory)

    for name, func in [("compatibility", cmd_compatibility), ("plugins", cmd_plugins), ("baseline", cmd_baseline), ("backup", cmd_backup), ("document", cmd_document)]:
        command = sub.add_parser(name)
        command.add_argument("--config", required=True)
        command.add_argument("--run-id", required=True)
        command.set_defaults(func=func)

    for name, func in [("endpoints", cmd_endpoints), ("logs", cmd_logs), ("database", cmd_database)]:
        command = sub.add_parser(name)
        command.add_argument("--config", required=True)
        command.add_argument("--run-id", required=True)
        command.add_argument("--phase", choices=["before", "after"], default="before")
        command.set_defaults(func=func)

    command = sub.add_parser("upgrade")
    command.add_argument("--config", required=True)
    command.add_argument("--run-id", required=True)
    command.add_argument("--approved", action="store_true")
    command.set_defaults(func=cmd_upgrade)

    command = sub.add_parser("validate")
    command.add_argument("--config", required=True)
    command.add_argument("--run-id", required=True)
    command.add_argument("--mode", choices=["upgrade", "rollback"], default="upgrade")
    command.set_defaults(func=cmd_validate)

    command = sub.add_parser("rollback")
    command.add_argument("--config", required=True)
    command.add_argument("--run-id", required=True)
    command.add_argument("--approved", action="store_true")
    command.add_argument("--force", action="store_true")
    command.set_defaults(func=cmd_rollback)

    command = sub.add_parser("compare")
    command.add_argument("--before", required=True)
    command.add_argument("--after", required=True)
    command.set_defaults(func=cmd_compare)

    command = sub.add_parser("orchestrate")
    command.add_argument("--config", required=True)
    command.add_argument("--run-id", required=True)
    command.add_argument("--workflow", choices=["upgrade", "rollback"], default="upgrade")
    command.add_argument("--agents-dir", default="agents")
    command.add_argument("--pre-upgrade-approved", action="store_true")
    command.add_argument("--acceptance-approved", action="store_true")
    command.add_argument("--rollback-approved", action="store_true")
    command.add_argument("--force-rollback", action="store_true")
    command.set_defaults(func=cmd_orchestrate)
    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        return args.func(args)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 64
    except FileNotFoundError as exc:
        print(f"evidence error: {exc}", file=sys.stderr)
        return 66
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 65


if __name__ == "__main__":
    raise SystemExit(main())
