# GitHub Copilot Multi-Agent Instructions

This project uses multiple AI coding agents in parallel. Follow these rules to prevent conflicts.

## Core Rule: Worktree Isolation

Every agent works in its own git worktree. Never work directly in the main repository clone.

## Starting Work

```bash
# Navigate to hub, sync main
cd ~/dev/projects/retail-store-scraper
git checkout main && git pull

# Create your worktree with unique branch
git worktree add ../retail-store-scraper--{type}-copilot-{task} -b {type}/copilot-{task}

# Work in the worktree
cd ../retail-store-scraper--{type}-copilot-{task}
```

## Branch Naming

Format: `{type}/copilot-{description}`

Examples:
- `feat/copilot-api-client`
- `fix/copilot-null-check`
- `refactor/copilot-utils`

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

## Commit Format

```
{type}: {description}

Agent: copilot
Co-Authored-By: GitHub Copilot <noreply@github.com>
```

## High-Conflict Files

Check if another agent is editing before modifying:
- `run.py`
- `config/retailers.yaml`
- `CLAUDE.md`
- `requirements.txt`

## Sync with Main

Always use merge (not rebase):

```bash
git fetch origin main
git merge origin/main
```

## PR Creation

```bash
gh pr create --title "{type}: {description}" --body "## Summary
- Description of changes

## Agent
copilot

## Test plan
- [ ] Verification steps
"
```

## Cleanup After Merge

```bash
cd ~/dev/projects/retail-store-scraper
git worktree remove ../retail-store-scraper--{branch}
git branch -d {branch}
```

## Full Documentation

See `.claude/rules/devops-workflow.md` for complete multi-agent workflow rules.
