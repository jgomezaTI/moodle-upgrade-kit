# Adding a new regression check

1. Give the check a stable ID.
2. Define whether it is `critical`, `warning`, or `info`.
3. Make the check deterministic where possible.
4. Define expected evidence and failure semantics.
5. Add a fixture/test if the check has parsing logic.
6. Add it to the relevant environment configuration.
7. Document why the check exists, ideally referencing the incident that introduced it.

A critical check failure must block an unattended upgrade.
