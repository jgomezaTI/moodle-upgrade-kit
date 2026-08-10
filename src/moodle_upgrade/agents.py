from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from .evidence import read_json
from .rollback import rollback_preconditions
from .upgrade import upgrade_preconditions


KNOWN_CAPABILITIES = {
    "moodle.inventory",
    "moodle.compatibility",
    "moodle.plugins",
    "moodle.baseline",
    "moodle.endpoints",
    "moodle.logs",
    "moodle.database",
    "moodle.backup",
    "moodle.upgrade",
    "moodle.validate",
    "moodle.rollback",
    "moodle.document",
}


class AgentContractError(ValueError):
    pass


@dataclass(frozen=True)
class AgentContract:
    id: str
    name: str
    version: str
    role: str
    effect: str
    execution: str
    allowed_capabilities: tuple[str, ...]
    forbidden_capabilities: tuple[str, ...]
    consumes: tuple[str, ...]
    produces: tuple[str, ...]
    delegates_to: tuple[str, ...]
    path: str


@dataclass(frozen=True)
class AgentRegistry:
    agents: dict[str, AgentContract]
    capability_owners: dict[str, str]

    def authorize(self, agent_id: str, capability: str) -> bool:
        agent = self.agents.get(agent_id)
        return bool(
            agent
            and capability in agent.allowed_capabilities
            and capability not in agent.forbidden_capabilities
            and self.capability_owners.get(capability) == agent_id
        )


def _frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, flags=re.DOTALL)
    if not match:
        raise AgentContractError(f"Agent contract has no YAML frontmatter: {path}")
    data = yaml.safe_load(match.group(1)) or {}
    if not isinstance(data, dict):
        raise AgentContractError(f"Agent contract frontmatter must be a mapping: {path}")
    return data


def _string_list(value: Any, field: str, path: Path) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise AgentContractError(f"{field} must be a list of non-empty strings: {path}")
    if len(set(value)) != len(value):
        raise AgentContractError(f"{field} contains duplicates: {path}")
    return tuple(value)


def load_agent_registry(agents_dir: str | Path = "agents") -> AgentRegistry:
    root = Path(agents_dir).resolve()
    manifest_path = root / "manifest.yml"
    if not manifest_path.is_file():
        raise AgentContractError(f"Agent manifest not found: {manifest_path}")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    entries = manifest.get("agents", [])
    if str(manifest.get("schema_version")) != "1.0" or not isinstance(entries, list) or not entries:
        raise AgentContractError("Agent manifest must use schema_version 1.0 and declare agents")

    agents: dict[str, AgentContract] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not isinstance(entry.get("contract"), str):
            raise AgentContractError("Each agent manifest entry requires id and contract")
        agent_id = entry["id"]
        contract_path = (root / entry["contract"]).resolve()
        try:
            contract_path.relative_to(root)
        except ValueError as exc:
            raise AgentContractError(f"Agent contract escapes agents directory: {entry['contract']}") from exc
        if not contract_path.is_file():
            raise AgentContractError(f"Agent contract not found: {contract_path}")
        data = _frontmatter(contract_path)
        if data.get("id") != agent_id:
            raise AgentContractError(f"Agent id does not match manifest entry: {contract_path}")
        if agent_id in agents:
            raise AgentContractError(f"Duplicate agent id: {agent_id}")
        allowed = _string_list(data.get("allowed_capabilities"), "allowed_capabilities", contract_path)
        forbidden = _string_list(data.get("forbidden_capabilities"), "forbidden_capabilities", contract_path)
        unknown = (set(allowed) | set(forbidden)) - KNOWN_CAPABILITIES
        if unknown:
            raise AgentContractError(f"Unknown capabilities in {contract_path}: {', '.join(sorted(unknown))}")
        overlap = set(allowed) & set(forbidden)
        if overlap:
            raise AgentContractError(f"Allowed and forbidden capabilities overlap in {contract_path}")
        required_fields = ("name", "version", "role", "effect", "execution")
        if any(not isinstance(data.get(field), str) or not data.get(field) for field in required_fields):
            raise AgentContractError(f"Agent contract is missing required identity fields: {contract_path}")
        agents[agent_id] = AgentContract(
            id=agent_id,
            name=data["name"],
            version=data["version"],
            role=data["role"],
            effect=data["effect"],
            execution=data["execution"],
            allowed_capabilities=allowed,
            forbidden_capabilities=forbidden,
            consumes=_string_list(data.get("consumes"), "consumes", contract_path),
            produces=_string_list(data.get("produces"), "produces", contract_path),
            delegates_to=_string_list(data.get("delegates_to"), "delegates_to", contract_path),
            path=str(contract_path.relative_to(root)),
        )

    for agent in agents.values():
        missing_delegates = set(agent.delegates_to) - set(agents)
        if missing_delegates:
            raise AgentContractError(f"Unknown delegates for {agent.id}: {', '.join(sorted(missing_delegates))}")

    capability_owners: dict[str, str] = {}
    for agent in agents.values():
        for capability in agent.allowed_capabilities:
            if capability in capability_owners:
                raise AgentContractError(f"Capability {capability} has multiple agent owners")
            capability_owners[capability] = agent.id
    missing_capabilities = KNOWN_CAPABILITIES - set(capability_owners)
    if missing_capabilities:
        raise AgentContractError("Capabilities without an agent owner: " + ", ".join(sorted(missing_capabilities)))
    if capability_owners.get("moodle.upgrade") != "upgrade-agent":
        raise AgentContractError("Only upgrade-agent may own moodle.upgrade")
    if capability_owners.get("moodle.rollback") != "rollback-agent":
        raise AgentContractError("Only rollback-agent may own moodle.rollback")
    orchestrator = agents.get("upgrade-orchestrator")
    if not orchestrator or orchestrator.execution != "delegate-only" or orchestrator.allowed_capabilities:
        raise AgentContractError("upgrade-orchestrator must be delegate-only with no direct capabilities")
    return AgentRegistry(agents=agents, capability_owners=capability_owners)


def _finding(code: str, message: str) -> dict[str, str]:
    return {"severity": "critical", "code": code, "message": message}


def orchestrate_agents(
    config: dict[str, Any],
    run_path: str | Path,
    *,
    workflow: str = "upgrade",
    pre_upgrade_approved: bool = False,
    acceptance_approved: bool = False,
    rollback_approved: bool = False,
    force_rollback: bool = False,
    agents_dir: str | Path = "agents",
) -> dict[str, Any]:
    """Select one permitted next capability from evidence; never execute it."""
    if workflow not in {"upgrade", "rollback"}:
        raise ValueError("workflow must be upgrade or rollback")
    registry = load_agent_registry(agents_dir)
    run_dir = Path(run_path)

    def load(name: str, fallback: str | None = None) -> Any:
        path = run_dir / name
        if path.is_file():
            return read_json(path)
        if fallback and (run_dir / fallback).is_file():
            return read_json(run_dir / fallback)
        return None

    def newer(name: str, anchor: str) -> bool:
        path, anchor_path = run_dir / name, run_dir / anchor
        return path.is_file() and anchor_path.is_file() and path.stat().st_mtime >= anchor_path.stat().st_mtime

    evidence_names = [
        "inventory-before.json", "compatibility.json", "plugins.json", "baseline-before.json", "backup.json",
        "upgrade-result.json", "rollback-result.json", "inventory-after.json", "endpoints-after.json",
        "logs-after.json", "database-after.json", "validation.json", "document-result.json",
    ]
    evidence = {name: (run_dir / name).is_file() for name in evidence_names}
    approvals = {
        "pre_upgrade": pre_upgrade_approved,
        "acceptance": acceptance_approved,
        "rollback": rollback_approved,
        "force_rollback": force_rollback,
    }

    def result(status: str, *, action: dict[str, Any] | None = None, blockers: list[dict[str, str]] | None = None, gate: str | None = None) -> dict[str, Any]:
        blockers = blockers or []
        return {
            "schema_version": "1.0",
            "workflow": workflow,
            "status": status,
            "current_agent": "upgrade-orchestrator",
            "next_action": action,
            "human_gate": gate,
            "blockers": blockers,
            "evidence": evidence,
            "approvals": approvals,
            "summary": {
                "blocked": bool(blockers),
                "action_required": action is not None,
                "complete": status == "complete",
            },
        }

    def action(capability: str, output: str, **parameters: Any) -> dict[str, Any]:
        owner = registry.capability_owners[capability]
        orchestrator = registry.agents["upgrade-orchestrator"]
        if owner not in orchestrator.delegates_to or not registry.authorize(owner, capability):
            raise AgentContractError(f"Agent policy denies delegation of {capability} to {owner}")
        return {
            "agent": owner,
            "capability": capability,
            "parameters": parameters,
            "expected_evidence": output,
            "requires_human_approval": capability in {"moodle.upgrade", "moodle.rollback"},
            "executes_automatically": False,
        }

    inventory = load("inventory-before.json", "inventory.json")
    if inventory is None:
        return result("action_required", action=action("moodle.inventory", "inventory-before.json", phase="before"))
    compatibility = load("compatibility.json")
    if compatibility is None and workflow == "upgrade":
        return result("action_required", action=action("moodle.compatibility", "compatibility.json"))
    plugins = load("plugins.json")
    if plugins is None and workflow == "upgrade":
        return result("action_required", action=action("moodle.plugins", "plugins.json"))
    baseline = load("baseline-before.json")
    if baseline is None:
        return result("action_required", action=action("moodle.baseline", "baseline-before.json"))
    backup = load("backup.json")
    if backup is None:
        return result("action_required", action=action("moodle.backup", "backup.json"))

    if workflow == "upgrade":
        blockers = upgrade_preconditions(config, True, inventory, compatibility, backup, baseline, plugins)
        if blockers:
            return result("blocked", blockers=blockers)
        if config.get("safety", {}).get("require_human_gate", True) and not pre_upgrade_approved:
            return result("human_gate", gate="pre-upgrade-review")
        upgrade_result = load("upgrade-result.json")
        if upgrade_result is None:
            return result("action_required", action=action("moodle.upgrade", "upgrade-result.json"))
        if not upgrade_result.get("summary", {}).get("completed", False):
            return result("blocked", blockers=upgrade_result.get("findings") or [_finding("UPGRADE_NOT_COMPLETED", "Upgrade evidence does not report completion.")])
        anchor = "upgrade-result.json"
    else:
        validation_before = load("validation.json")
        blockers = rollback_preconditions(config, True, backup, validation_before, force_rollback)
        if blockers:
            return result("blocked", blockers=blockers)
        if config.get("safety", {}).get("require_human_gate", True) and not rollback_approved:
            return result("human_gate", gate="rollback-review")
        rollback_result = load("rollback-result.json")
        if rollback_result is None:
            return result("action_required", action=action("moodle.rollback", "rollback-result.json", force=force_rollback))
        if not rollback_result.get("summary", {}).get("restored", False):
            return result("blocked", blockers=rollback_result.get("findings") or [_finding("ROLLBACK_NOT_RESTORED", "Rollback evidence does not report a restored state.")])
        anchor = "rollback-result.json"

    post_actions = [
        ("inventory-after.json", "moodle.inventory", {"phase": "after"}),
        ("endpoints-after.json", "moodle.endpoints", {"phase": "after"}),
        ("logs-after.json", "moodle.logs", {"phase": "after"}),
        ("database-after.json", "moodle.database", {"phase": "after"}),
    ]
    for name, capability, parameters in post_actions:
        if not newer(name, anchor):
            return result("action_required", action=action(capability, name, **parameters))

    validation = load("validation.json")
    expected_mode = workflow
    latest_post = max(post_actions, key=lambda item: (run_dir / item[0]).stat().st_mtime)[0]
    if validation is None or validation.get("mode") != expected_mode or not newer("validation.json", latest_post):
        return result("action_required", action=action("moodle.validate", "validation.json", mode=expected_mode))
    if not validation.get("summary", {}).get("accepted", False):
        return result("blocked", blockers=validation.get("findings") or [_finding("VALIDATION_NOT_ACCEPTED", "Post-change validation was not accepted.")])
    if workflow == "upgrade" and config.get("safety", {}).get("require_human_gate", True) and not acceptance_approved:
        return result("human_gate", gate="acceptance")
    if not newer("document-result.json", "validation.json"):
        return result("action_required", action=action("moodle.document", "document-result.json"))
    document = load("document-result.json")
    if not document or not document.get("summary", {}).get("report_generated", False):
        return result("blocked", blockers=[_finding("DOCUMENTATION_NOT_COMPLETED", "Documentation evidence does not report a generated report.")])
    return result("complete")
