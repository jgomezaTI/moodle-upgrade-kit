# Environment configuration

Create one YAML file per Moodle instance, for example:

- `enaex-es-staging.yml`
- `enaex-es-production.yml`
- `enaex-en-production.yml`

Never commit passwords, private keys, bearer tokens, database DSNs containing credentials, or Google/GitHub access tokens.

Use environment variables or an approved secret manager for secrets. Files ending in `.local.yml` are ignored by Git.
