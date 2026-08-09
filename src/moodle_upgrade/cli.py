from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

from .config import load_config, ConfigError
from .evidence import run_dir, write_json, read_json
from .endpoints import run_endpoint_checks
from .logs import analyze_files
from .compare import compare_endpoint_sets


def cmd_validate_config(args):
    load_config(args.config)
    print("config: OK")
    return 0


def cmd_new_run(args):
    cfg = load_config(args.config)
    rid = args.run_id or datetime.now(timezone.utc).strftime("UPG-%Y%m%d-%H%M%S")
    rd = run_dir(rid)
    payload = {
        "run_id": rid,
        "project": cfg["project"],
        "target_version": cfg["moodle"]["target_version"],
        "moodle_root": cfg["moodle"]["root"],
        "base_url": cfg["moodle"]["base_url"],
    }
    write_json(rd / "metadata.json", payload)
    print(rid)
    return 0


def cmd_endpoints(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    results = run_endpoint_checks(cfg)
    suffix = "before" if args.phase == "before" else "after"
    write_json(rd / f"endpoints-{suffix}.json", results)
    print(json.dumps(results, indent=2))
    return 0 if all(x.get("ok") for x in results) else 2


def cmd_logs(args):
    cfg = load_config(args.config)
    rd = run_dir(args.run_id)
    logs_cfg = cfg.get("logs", {})
    results = analyze_files(logs_cfg.get("files", []), logs_cfg.get("patterns", {}))
    suffix = "before" if args.phase == "before" else "after"
    write_json(rd / f"logs-{suffix}.json", results)
    print(json.dumps(results, indent=2))
    return 0


def cmd_compare(args):
    before = read_json(args.before)
    after = read_json(args.after)
    result = compare_endpoint_sets(before, after)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 3


def build_parser():
    p = argparse.ArgumentParser(prog="muk")
    sub = p.add_subparsers(dest="cmd", required=True)

    x = sub.add_parser("validate-config")
    x.add_argument("--config", required=True)
    x.set_defaults(func=cmd_validate_config)

    x = sub.add_parser("new-run")
    x.add_argument("--config", required=True)
    x.add_argument("--run-id")
    x.set_defaults(func=cmd_new_run)

    x = sub.add_parser("endpoints")
    x.add_argument("--config", required=True)
    x.add_argument("--run-id", required=True)
    x.add_argument("--phase", choices=["before", "after"], default="before")
    x.set_defaults(func=cmd_endpoints)

    x = sub.add_parser("logs")
    x.add_argument("--config", required=True)
    x.add_argument("--run-id", required=True)
    x.add_argument("--phase", choices=["before", "after"], default="before")
    x.set_defaults(func=cmd_logs)

    x = sub.add_parser("compare")
    x.add_argument("--before", required=True)
    x.add_argument("--after", required=True)
    x.set_defaults(func=cmd_compare)
    return p


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        return args.func(args)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    raise SystemExit(main())
