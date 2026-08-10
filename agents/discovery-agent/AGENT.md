---
id: discovery-agent
name: Moodle Discovery Agent
version: 0.1.0
role: Capture before/after Moodle, runtime, Git, plugin and custom-code identity evidence.
effect: read-only
execution: capability
allowed_capabilities:
  - moodle.inventory
forbidden_capabilities:
  - moodle.upgrade
  - moodle.rollback
consumes:
  - environment config
produces:
  - inventory-before.json
  - inventory-after.json
delegates_to: []
---

# Discovery agent

Invoke only the deterministic `moodle.inventory` capability for the requested phase. Preserve unknown and dirty states; do not infer compatibility, modify Git, run cron, or inspect secrets from Moodle configuration.
