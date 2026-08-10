# Plan: Evidence-driven Moodle agent layer

## Architecture

1. Store portable agent prompts/contracts under `agents/<agent-id>/AGENT.md` with machine-readable YAML frontmatter.
2. Register contracts in `agents/manifest.yml`; validate safe paths, identities, capabilities, ownership and delegation at load time.
3. Factor public read-only precondition evaluators from upgrade and rollback so execution and orchestration share one source of truth.
4. Implement a deterministic state selector in `src/moodle_upgrade/agents.py`. It reads evidence and returns one decision; it never invokes a capability.
5. Expose the selector through `muk orchestrate` and `speckit.moodle.orchestrate`.
6. Persist the latest decision as `runs/<run-id>/agent-state.json`.

## Safety design

- The orchestrator is `delegate-only` and has an empty allowed-capability set.
- Capability ownership is unique; upgrade and rollback ownership is hard-validated.
- Human approvals are decision inputs, not persisted authorization and not machine-gate overrides.
- Destructive steps retain the existing CLI/config/evidence gates after delegation.
- Agent decisions set `executes_automatically: false`.

## Verification

- Contract/permission tests.
- Upgrade and rollback gate-selection tests.
- Existing destructive runner sentinel tests.
- Full pytest, config validation, diff checks and real read-only orchestration against the existing Enaex evidence.
