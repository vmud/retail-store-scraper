# 1Password Integration for GitHub Actions

This document describes how to securely access secrets from 1Password in GitHub Actions workflows.

## Overview

The repository uses 1Password Service Accounts to provide secure secret access to GitHub Actions. This eliminates the need to store sensitive credentials directly in GitHub Secrets while providing:

- Centralized secret management in 1Password
- Audit logs for secret access
- Easy rotation without updating GitHub
- Vault-level access control

## Prerequisites

1. **1Password Business or Teams** account
2. **1Password Service Account** with access to the required vault(s)
3. **GitHub Secret**: `OP_SERVICE_ACCOUNT_TOKEN` containing the service account token

## Setup Guide

### 1. Create a 1Password Service Account

1. Go to your 1Password admin console
2. Navigate to **Integrations** → **Directory**
3. Click **New Service Account**
4. Name it (e.g., `github-actions-scraper`)
5. Grant access to the vault(s) containing your secrets
6. Copy the generated token (you'll only see this once!)

### 2. Store the Token in GitHub

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `OP_SERVICE_ACCOUNT_TOKEN`
5. Value: Paste the service account token
6. Click **Add secret**

### 3. Organize Secrets in 1Password

The repository uses the following 1Password vault structure:

```
Vault: DEV
├── OXYLABS_RESIDENTIAL
│   ├── username
│   └── credential (password)
├── OXYLABS_SCRAPER_API
│   ├── username
│   └── credential (password)
├── GCS-ServiceAccount (optional)
│   └── credential (JSON key)
└── CODECOV_TOKEN (optional)
    └── credential
```

## Usage in Workflows

### Basic Pattern

Add this step to any workflow that needs secrets:

```yaml
- name: Load secrets from 1Password
  uses: 1password/load-secrets-action@v2
  with:
    export-env: true
  env:
    OP_SERVICE_ACCOUNT_TOKEN: ${{ secrets.OP_SERVICE_ACCOUNT_TOKEN }}
    # Oxylabs Residential Proxy
    OXYLABS_RESIDENTIAL_USERNAME: op://DEV/OXYLABS_RESIDENTIAL/username
    OXYLABS_RESIDENTIAL_PASSWORD: op://DEV/OXYLABS_RESIDENTIAL/credential
```

### Secret Reference Syntax

Format: `op://vault-name/item-name/field-name`

| Component | Description | Example |
|-----------|-------------|---------|
| `vault-name` | Name of the 1Password vault | `Scraper`, `DevOps` |
| `item-name` | Name of the item in the vault | `Oxylabs`, `GCS-ServiceAccount` |
| `field-name` | Field within the item | `password`, `username`, `credential` |

### Multi-line Secrets (JSON keys, certificates)

For multi-line values like GCS service account keys:

```yaml
- name: Load GCS credentials
  uses: 1password/load-secrets-action@v2
  with:
    export-env: true
  env:
    OP_SERVICE_ACCOUNT_TOKEN: ${{ secrets.OP_SERVICE_ACCOUNT_TOKEN }}
    GCS_SERVICE_ACCOUNT_KEY: op://DEV/GCS-ServiceAccount/credential

- name: Write GCS key to file
  run: |
    echo "$GCS_SERVICE_ACCOUNT_KEY" > /tmp/gcs-key.json
    echo "GCS_SERVICE_ACCOUNT_KEY=/tmp/gcs-key.json" >> $GITHUB_ENV
```

### Using with Reusable Workflow

The repository includes a reusable workflow at `.github/workflows/1password-secrets.yml`:

```yaml
jobs:
  setup:
    uses: ./.github/workflows/1password-secrets.yml
    secrets: inherit

  build:
    needs: setup
    runs-on: ubuntu-latest
    steps:
      # Secrets are loaded, proceed with build
      - uses: actions/checkout@v6
```

## Available Workflows

| Workflow | Purpose |
|----------|---------|
| `1password-secrets.yml` | Reusable workflow for loading secrets |
| `scraper-proxy-test.yml` | Example integration test using proxy secrets |

## Security Best Practices

1. **Minimal Permissions**: Grant service accounts access only to vaults they need
2. **Separate Vaults**: Use dedicated vaults for CI/CD secrets vs. personal credentials
3. **Audit Regularly**: Review 1Password audit logs for service account activity
4. **Rotate Tokens**: Periodically rotate service account tokens
5. **Never Log Secrets**: The action masks secrets automatically, but avoid `echo $SECRET`

## Troubleshooting

### "Secret not found" Error

```
Error: Secret op://Vault/Item/field not found
```

**Solutions:**
- Verify the vault name, item name, and field name match exactly (case-sensitive)
- Confirm the service account has access to the vault
- Check if the item exists in 1Password

### "Invalid token" Error

```
Error: Invalid service account token
```

**Solutions:**
- Regenerate the service account token in 1Password
- Update `OP_SERVICE_ACCOUNT_TOKEN` in GitHub Secrets
- Verify no extra whitespace in the token

### Testing Locally

You can test 1Password references locally with the CLI:

```bash
# Install 1Password CLI
# macOS: brew install --cask 1password/tap/1password-cli

# Sign in with service account
export OP_SERVICE_ACCOUNT_TOKEN="your-token-here"

# Test a reference
op read "op://Scraper/Oxylabs/residential-username"
```

## Secrets Reference

| Environment Variable | 1Password Reference | Description |
|---------------------|---------------------|-------------|
| `OXYLABS_RESIDENTIAL_USERNAME` | `op://DEV/OXYLABS_RESIDENTIAL/username` | Residential proxy username |
| `OXYLABS_RESIDENTIAL_PASSWORD` | `op://DEV/OXYLABS_RESIDENTIAL/credential` | Residential proxy password |
| `OXYLABS_SCRAPER_API_USERNAME` | `op://DEV/OXYLABS_SCRAPER_API/username` | Web Scraper API username |
| `OXYLABS_SCRAPER_API_PASSWORD` | `op://DEV/OXYLABS_SCRAPER_API/credential` | Web Scraper API password |
| `GCS_SERVICE_ACCOUNT_KEY` | `op://DEV/GCS-ServiceAccount/credential` | GCS service account JSON (if configured) |
| `CODECOV_TOKEN` | `op://DEV/CODECOV_TOKEN/credential` | Codecov upload token (if configured) |

## Migration from GitHub Secrets

To migrate existing GitHub Secrets to 1Password:

1. Create corresponding items in your 1Password vault
2. Update workflows to use `1password/load-secrets-action`
3. Test the workflow with `workflow_dispatch`
4. Once verified, delete the old GitHub Secrets

## References

- [1Password GitHub Action Documentation](https://developer.1password.com/docs/ci-cd/github-actions/)
- [1Password Service Accounts](https://developer.1password.com/docs/service-accounts/)
- [Secret Reference Syntax](https://developer.1password.com/docs/cli/secret-references/)
