# Specification: Evidence-driven Moodle agent layer

## Intent

Add a vendor-neutral, Spec Kit-style agent layer that helps an AI integration progress a Moodle upgrade by consuming deterministic evidence, selecting one safe next capability and stopping at machine or human gates. The framework must remain generic across Moodle versions and environments.

## User stories

1. As an upgrade owner, I can ask the orchestrator for the next step and receive one agent/capability pair backed by the current run evidence.
2. As a reviewer, I can see which evidence each agent consumes and produces and which capabilities it is forbidden to invoke.
3. As an environment owner, I know that only the upgrade agent can request upgrade and only the rollback agent can request rollback, and neither action executes automatically.
4. As a developer repairing incompatible custom code, I can use the compatibility agent's deterministic findings and grouped review evidence without losing severity or traceability.

## Functional requirements

- **AR-001** Seven contracts exist: upgrade-orchestrator, discovery-agent, compatibility-agent, baseline-agent, upgrade-agent, rollback-agent and documentation-agent.
- **AR-002** All 12 deterministic Moodle capabilities have exactly one agent owner.
- **AR-003** The orchestrator owns no capability and delegates only to registered agents.
- **AR-004** `moodle.upgrade` and `moodle.rollback` have exclusive, separate owners.
- **AR-005** The next-step selector consumes existing run artifacts and invokes the same deterministic upgrade/rollback precondition evaluators as execution.
- **AR-006** A decision contains status, blocker codes, approvals, evidence presence and at most one non-auto-executing next action.
- **AR-007** Missing pre-change evidence is collected in critical-path order before mutation is considered.
- **AR-008** Failed machine gates stop orchestration even when human approval input is true.
- **AR-009** Post-change evidence must be newer than the upgrade/rollback result, and validation/documentation must be newer than their prerequisites.
- **AR-010** The agent layer is exposed through a Spec Kit extension command and a deterministic CLI command.

## Non-goals

- Bundling or selecting a particular LLM runtime.
- Automatically applying plugin fixes.
- Enabling mutation or inventing upgrade/restore commands.
- Reimplementing inventory, compatibility, plugin, baseline, backup, validation, upgrade or rollback logic in prompts.

## Acceptance criteria

- Registry validation rejects ambiguous, unknown or escaping contracts.
- Permission tests prove destructive capabilities cannot cross agent boundaries.
- Real Enaex evidence produces `blocked` with mutation, Git, compatibility, backup and missing-command blockers while `safety.allow_mutation` remains false.
- The complete repository test suite and example/local config validation pass.
