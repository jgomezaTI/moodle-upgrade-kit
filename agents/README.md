# Moodle Upgrade Agents

This directory is the portable agent-contract layer. It does not contain a model runtime and does not replace the deterministic code under `src/moodle_upgrade/`.

`manifest.yml` registers seven `AGENT.md` contracts. Their YAML frontmatter defines identity, effect, execution mode, allowed/forbidden capabilities, evidence inputs/outputs and delegation. The Markdown body tells any compatible coding agent how to use that bounded role.

The policy is machine-enforced:

```text
upgrade-orchestrator  delegate-only; no direct capability
discovery-agent       moodle.inventory
compatibility-agent   moodle.compatibility, moodle.plugins
baseline-agent        moodle.baseline/endpoints/logs/database/backup/validate
upgrade-agent         moodle.upgrade only
rollback-agent        moodle.rollback only
documentation-agent   moodle.document
```

Run `muk orchestrate` to produce `agent-state.json`. A decision may request one action, pause at a human gate, report blockers or report completion. It never executes the requested capability automatically.

Compatibility findings and plugin risk groups are suitable inputs for AI-assisted remediation review. Applying source patches remains a separate explicitly authorized development action; it is never implied by an operational upgrade run.

To start that review from the environment YAML, run `muk review-code --config <yaml> --run-id <id>` or invoke `speckit.moodle.review-code` through the active Spec Kit integration. The generated `code-review.json` records configured-path coverage and the compatibility agent's ordered work queue.
