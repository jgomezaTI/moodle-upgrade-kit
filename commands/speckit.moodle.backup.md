---
description: "Run the moodle.backup capability with evidence and safety controls."
---

# speckit.moodle.backup

## User input

$ARGUMENTS

## Authoritative contract

Read `.specify/extensions/moodle/skills/moodle.backup/SKILL.md` and follow it as the authoritative procedure for this command.

Before acting:

1. Parse `$ARGUMENTS` for `--config`, `--run-id`, phase/mode flags and explicit approval markers.
2. Resolve the project root and the installed extension directory.
3. Read `.specify/extensions/moodle/docs/CONSTITUTION.md` and obey its safety constraints.
4. Resolve or create the run ID when the command produces evidence.
5. For any destructive capability, do not execute mutation unless the current workflow/run contains explicit human approval and configuration permits mutation.

Execute the `moodle.backup` contract and write its declared evidence artifact(s) under `runs/<run-id>/`.
