---
name: secrets
description: Manage encrypted secrets between the master vault and projects using SOPS/Age.
---

# /secrets — SOPS/Age Secret Management

Manage encrypted secrets between the master vault and projects.

## Master Vault

Location: `~/github/oneshot/secrets/`
Encryption: SOPS + Age (config in `~/github/oneshot/.sops.yaml`)

## CLI Commands

The `secrets` CLI (at `~/.local/bin/secrets`) works from any directory.

```bash
# Read a single key
secrets get EXA_API_KEY

# List all vault files and their keys
secrets list

# Decrypt a full file to stdout
secrets decrypt research_keys

# Add/update a key (non-interactive, no commit)
secrets set research_keys 'NEW_KEY=value'

# Add/update + commit + push
secrets set research_keys 'NEW_KEY=value' --commit

# Bootstrap .env in a project from the vault
cd ~/github/myproject && secrets init services
```

## Pull Secrets into a Project

1. Identify which secrets the project needs (check `.env.example` or imports)
2. Run `secrets init <namespace>` to write `.env` from the vault
3. Verify the app can start with the new secrets

## Push New Secrets to the Vault

1. Add/update: `secrets set <namespace> 'KEY=value'`
2. Commit when ready: `secrets set <namespace> 'KEY=value' --commit`

## Common Patterns

```bash
# Find which vault file contains a key
secrets list | grep -i brave

# Extract a key for use in a script
BRAVE_KEY=$(secrets get BRAVE_API_KEY)

# View all keys in a namespace
secrets decrypt research_keys
```

## How It Works

- Vault files are SOPS-encrypted dotenv at `~/github/oneshot/secrets/*.encrypted`
- `secrets get` searches all vault files for the key
- `secrets set` decrypts the file, merges the new key, re-encrypts
- `secrets init` decrypts a vault file to `.env` in the current directory
- Age key lives at `~/.age/key.txt`

## Safety Rules

- Never display secret values in output
- Always verify `.env` is in `.gitignore` before writing
- Namespace secrets by project in the vault
- Never commit plaintext secrets
- Never suggest `.env` files without encryption

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `no matching creation rules found` | Input file must end in `.encrypted` (handled by the CLI automatically) |
| `key not found in any vault file` | Key doesn't exist in any vault — add it with `secrets set` |
| `file not found` | Check `secrets list` for available namespaces |
