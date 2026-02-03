# Multi-Agent DevOps Workflow Rules

These rules define the development workflow for teams using multiple AI coding agents (Claude Code, Cursor, Copilot, Gemini, Aider, etc.) in parallel. The core architecture uses **git worktrees** to isolate each agent's work and prevent conflicts.

## 1. Worktree Isolation Architecture

### The Hub-and-Spoke Model

```
~/dev/projects/
├── retail-store-scraper/                    # Hub (main branch, always clean)
├── retail-store-scraper--feat-cc1-export/   # Claude Code agent 1 worktree
├── retail-store-scraper--fix-cursor-bug/    # Cursor agent worktree
└── retail-store-scraper--feat-copilot-api/  # Copilot agent worktree
```

### Core Principles

- **Every agent works in its own worktree** - never share a working directory
- **Hub stays on main** - the primary clone is read-only for reference
- **Naming convention**: `{repo}--{branch-name}` for worktree directories
- **One branch per task** - no shared branches between agents

### Why Worktrees?

| Problem with Branches Alone | Worktree Solution |
|---------------------------|-------------------|
| Uncommitted changes block checkout | Each agent has independent working directory |
| Stash conflicts between agents | No shared state to conflict |
| Mixed staged/unstaged changes | Clean separation per task |
| IDE/tool state leakage | Isolated tool configurations |

## 2. Pre-Work Protocol

### Starting Any New Task

Before writing any code, every agent MUST:

```bash
# 1. Navigate to hub and sync
cd ~/dev/projects/retail-store-scraper
git checkout main && git pull

# 2. Create worktree with unique branch
git worktree add ../retail-store-scraper--{branch-name} -b {type}/{agent-id}-{description}

# 3. Navigate to worktree
cd ../retail-store-scraper--{branch-name}

# 4. Verify isolation
git branch  # Should show your unique branch
pwd         # Should be in worktree directory
```

### Branch Naming Convention

```
{type}/{agent-id}-{short-description}
```

**Types:**
- `feat/` - New feature
- `fix/` - Bug fix
- `refactor/` - Code restructuring
- `test/` - Test additions/changes
- `docs/` - Documentation
- `chore/` - Build, deps, config

**Agent IDs:**
| Agent | ID | Example Branch |
|-------|----|--------------------|
| Claude Code (session 1) | `cc1` | `feat/cc1-export-formats` |
| Claude Code (session 2) | `cc2` | `fix/cc2-csv-encoding` |
| Cursor | `cursor` | `feat/cursor-dashboard` |
| GitHub Copilot | `copilot` | `refactor/copilot-utils` |
| Google Gemini | `gemini` | `feat/gemini-api-client` |
| Aider | `aider` | `fix/aider-memory-leak` |
| Human (direct) | `human` | `feat/human-config-update` |

### When an Agent Starts a Session

1. **Check for existing work**: Look for worktrees with your agent ID
2. **Resume if exists**: `cd ../retail-store-scraper--{existing-branch}`
3. **Create new if starting fresh**: Follow pre-work protocol above

## 3. During-Work Rules

### File Ownership (Honor System)

When multiple agents are active simultaneously:

1. **Check before editing shared files**:
   ```bash
   # From hub, see all active branches
   git worktree list
   git branch -a | grep -E "(feat|fix|refactor)/"
   ```

2. **Avoid touching files another agent is likely editing**:
   - If Agent A is working on `feat/cc1-export`, avoid `export_service.py`
   - If unsure, communicate through PR comments or commit messages

3. **High-conflict files** (require extra caution):
   - `run.py` - main entry point
   - `config/retailers.yaml` - shared config
   - `CLAUDE.md` - project instructions
   - `requirements.txt` - dependencies

### Commit Practices

```bash
# Commit message format with agent ID
git commit -m "{type}: {description}

{optional body}

Agent: {agent-id}
Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

**Commit frequency:**
- After each logical unit of work
- Before switching focus within the task
- Every 15-20 minutes of active development

### Push Practices

```bash
# First push (set upstream)
git push -u origin {branch-name}

# Subsequent pushes
git push
```

**Push frequency:**
- After every 2-3 commits
- Before taking any break
- Before syncing with main

### Syncing with Main (When Needed)

Use **merge** (not rebase) to sync with main to preserve parallel history:

```bash
# From your worktree
git fetch origin main
git merge origin/main

# If conflicts, resolve then:
git add .
git commit -m "chore: Merge main into {branch}

Agent: {agent-id}"
git push
```

## 4. Merge Coordination

### Mode A: Manual Review (Human Controls)

The human operator reviews and merges all PRs:

1. Agent completes work, creates PR
2. Human reviews PR, checks for conflicts with other open PRs
3. Human merges in order of completion/priority
4. Other agents pull latest main

### Mode B: Coordinator Agent

Designate one agent session as "coordinator":

1. Coordinator monitors all open PRs
2. Runs conflict detection before approving merges
3. Sequences merges to minimize conflicts
4. Notifies other agents when main updates

### Mode C: PR-Based CI (Preferred)

Let GitHub Actions manage coordination:

1. PRs trigger automated checks
2. CI detects conflicts with other open PRs
3. Auto-merge when all checks pass
4. Labels indicate agent and status

### Conflict Escalation

| Level | Situation | Action |
|-------|-----------|--------|
| 0 | No conflicts | Auto-merge or approve |
| 1 | Minor conflicts (imports, config) | Agent resolves in PR branch |
| 2 | Moderate conflicts (shared code) | Human reviews resolution |
| 3 | Major conflicts (architecture) | Pause both PRs, human decides priority |

## 5. CI/CD Integration

### PR Labels for Multi-Agent Coordination

| Label | Meaning |
|-------|---------|
| `agent:claude-code` | Created by Claude Code |
| `agent:cursor` | Created by Cursor |
| `agent:copilot` | Created by GitHub Copilot |
| `conflict:detected` | Conflicts with another PR |
| `conflict:resolved` | Conflicts manually resolved |
| `ready:merge` | Approved and ready to merge |
| `needs:rebase` | Main has updated, needs sync |

### GitHub Actions Workflow

The `multi-agent-pr.yml` workflow handles:

1. **Conflict Detection**: Checks if PR conflicts with other open PRs
2. **Test Execution**: Runs full test suite
3. **Auto-labeling**: Applies agent labels based on branch prefix
4. **Merge Queue**: Sequences merges when multiple PRs ready

## 6. Cleanup Protocol

### After PR Merge

```bash
# From hub
cd ~/dev/projects/retail-store-scraper

# Remove worktree
git worktree remove ../retail-store-scraper--{branch-name}

# Delete local branch
git branch -d {branch-name}

# Prune remote tracking branches
git fetch --prune
```

### Detecting Stale Worktrees

```bash
# List all worktrees
git worktree list

# Find worktrees for merged branches
git worktree list | while read path branch rest; do
  branch_name=$(echo "$branch" | tr -d '[]')
  if git branch --merged main | grep -q "$branch_name"; then
    echo "STALE: $path ($branch_name merged to main)"
  fi
done
```

### Weekly Cleanup Routine

1. Check for merged branches still having worktrees
2. Remove orphaned worktrees: `git worktree prune`
3. Delete merged local branches
4. Verify hub is clean: `git status` should be empty

## 7. Quick Reference

### Starting Work

```bash
cd ~/dev/projects/retail-store-scraper
git checkout main && git pull
git worktree add ../retail-store-scraper--feat-{agent}-{task} -b feat/{agent}-{task}
cd ../retail-store-scraper--feat-{agent}-{task}
```

### During Work

```bash
git add {files}
git commit -m "feat: Description

Agent: {agent-id}
Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
git push -u origin feat/{agent}-{task}  # First time
git push                                 # Subsequent
```

### Finishing Work

```bash
# Create PR
gh pr create --title "feat: Description" --body "..."

# After merge, cleanup
cd ~/dev/projects/retail-store-scraper
git worktree remove ../retail-store-scraper--feat-{agent}-{task}
git branch -d feat/{agent}-{task}
git pull
```

## 8. Troubleshooting

### "Branch already exists"

```bash
# Check if worktree exists
git worktree list | grep {branch-name}

# If yes, navigate to it instead of creating new
cd ../retail-store-scraper--{branch-name}

# If no worktree but branch exists remotely
git worktree add ../retail-store-scraper--{branch-name} {branch-name}
```

### "Worktree already locked"

```bash
# Force unlock
git worktree unlock ../retail-store-scraper--{branch-name}

# Or remove if abandoned
git worktree remove --force ../retail-store-scraper--{branch-name}
```

### Conflicts During Merge to Main

1. Do NOT resolve in the PR branch during multi-agent work
2. Pull latest main into your branch first
3. If still conflicting with another PR, coordinate with that agent
4. Human may need to prioritize which PR merges first

## 9. Example Multi-Agent Workflow

### Scenario: 3 Agents Working Simultaneously

```
Agent CC1: Adding CSV export feature
Agent Cursor: Fixing authentication bug
Agent Copilot: Refactoring utility functions
```

### Timeline

```
T+0:  CC1 creates worktree, branch feat/cc1-csv-export
      Cursor creates worktree, branch fix/cursor-auth-bug
      Copilot creates worktree, branch refactor/copilot-utils

T+30: CC1 pushes first commits
      Cursor pushes first commits

T+45: Copilot pushes (touches utils.py - shared file)

T+60: CC1 creates PR, CI runs
      Cursor creates PR, CI detects no conflicts

T+75: Cursor PR approved, merged to main
      CC1 CI re-runs, detects needs-rebase

T+80: CC1 merges main into branch, resolves minor conflicts
      CC1 pushes, CI passes

T+90: CC1 PR approved, merged
      Copilot CI detects conflict with merged utils.py changes

T+100: Copilot merges main, resolves conflicts
       Copilot creates PR, CI passes, merged

T+120: All agents clean up worktrees
       Hub updated with all changes
```

## 10. Commit Message Template

```
{type}: {short description}

{optional detailed description}

Agent: {agent-id}
Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `style`

**Agent IDs:** `cc1`, `cc2`, `cursor`, `copilot`, `gemini`, `aider`, `human`
