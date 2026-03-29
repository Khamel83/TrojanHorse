---
name: secrets
description: Manage encrypted secrets between the master vault and projects using SOPS/Age.
---

# /secrets — SOPS/Age Secret Management

Manage encrypted secrets between the master vault and projects.

## Master Vault

Location: `~/github/oneshot/secrets/`
Encryption: SOPS + Age (config in `~/github/oneshot/.sops.yaml`)

## Pull Secrets into Project

1. Identify which secrets this project needs (check .env.example or imports)
2. Decrypt from vault:
   ```bash
   sops --config ~/github/oneshot/secrets/.sops.yaml -d ~/github/oneshot/secrets/<namespace>.enc.env
   ```
3. Write to project `.env` (must be gitignored)
4. Verify the app can start with the new secrets

## Push New Secrets to Vault

1. Identify new secrets (diff .env against vault)
2. Encrypt and add:
   ```bash
   sops --config ~/github/oneshot/secrets/.sops.yaml -e ~/github/oneshot/secrets/<namespace>.enc.env
   ```
3. Commit the encrypted file to oneshot repo

## Common Operations

```bash
# Decrypt and view (works from any directory)
sops --config ~/github/oneshot/secrets/.sops.yaml -d ~/github/oneshot/secrets/research_keys.env.encrypted

# Edit in-place (opens in $EDITOR)
sops --config ~/github/oneshot/secrets/.sops.yaml ~/github/oneshot/secrets/research_keys.env.encrypted

# Extract single key to variable
EXA_KEY=$(sops --config ~/github/oneshot/secrets/.sops.yaml -d --output-type json ~/github/oneshot/secrets/research_keys.json.encrypted | jq -r '.EXA_API_KEY')

# Create new encrypted file
sops -e --age $(cat ~/.sops/age/keys.txt | grep public | cut -d: -f2) plaintext.env > encrypted.enc.env
```

## Safety Rules

- Never display secret values in output
- Always verify .env is in .gitignore before writing
- Namespace secrets by project in the vault
- Never commit plaintext secrets
- Never suggest .env files without encryption
