# DevOps Workflow Rules

These rules define the development workflow for maintaining code quality, version control hygiene, and collaboration best practices. Apply these automatically without the user needing to ask.

## 1. Branch Management

### Create Feature Branches
- **Always** create a new branch before starting any feature or significant change
- Branch naming convention: `{type}/{short-description}`
  - Types: `feat/`, `fix/`, `refactor/`, `docs/`, `test/`, `chore/`
  - Examples: `feat/export-formats`, `fix/csv-encoding`, `refactor/scraper-interface`
- Create branch from the main branch (usually `main`)

### When to Create a Branch
- Before writing any new code for a feature
- Before making bug fixes
- Before refactoring existing code
- **Exception**: Documentation-only changes to README/CLAUDE.md can be made directly if minor

## 2. Commit Practices

### Commit Frequently
- Commit after completing each logical unit of work
- Commit when:
  - A new file is created and functional
  - A feature milestone is reached
  - Tests are passing for a component
  - Before switching to a different part of the codebase

### Commit Message Format
```
<type>: <short description>

<optional body explaining what and why>

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code restructuring without behavior change
- `test`: Adding or updating tests
- `docs`: Documentation changes
- `chore`: Build, dependencies, config changes
- `style`: Formatting, no code change

### Commit Granularity
- One commit per logical change (not one giant commit at the end)
- Keep commits atomic and reversible
- Avoid mixing unrelated changes in a single commit

## 3. Push Practices

### Push Regularly
- Push to remote after every 2-3 commits
- Push at natural breakpoints (end of a phase, before taking a break)
- Push before asking for user review
- Always push before creating a PR

### Push with Upstream Tracking
- Use `git push -u origin <branch>` for new branches
- This enables `git push` without arguments for subsequent pushes

## 4. Pull Request Standards

### When to Create a PR
- After completing all planned changes for a feature
- After all tests pass
- After code has been pushed to remote

### PR Title Format
```
<type>: <concise description of what the PR accomplishes>
```

### PR Body Structure
```markdown
## Summary
<1-3 bullet points describing the changes>

## Changes
- List of specific changes made
- Grouped by area (e.g., Backend, Frontend, Tests)

## Test plan
- [ ] How to verify the changes work
- [ ] What commands to run
- [ ] What to look for in the UI

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

### PR Quality Checklist
Before creating PR, ensure:
- [ ] All new code has been tested
- [ ] No console.log/print debug statements left behind
- [ ] No commented-out code
- [ ] Imports are organized
- [ ] No obvious typos in user-facing strings
- [ ] Documentation updated if needed

## 5. Workflow Integration

### At Feature Start
1. Check current branch: `git branch`
2. Ensure main is up to date: `git checkout main && git pull`
3. Create feature branch: `git checkout -b feat/feature-name`

### During Development
1. Work on logical chunks
2. Commit after each chunk: `git add . && git commit -m "..."`
3. Push after 2-3 commits: `git push`

### At Feature End
1. Run tests: `pytest tests/` (Python) or `npm test` (JS)
2. Final commit with any last changes
3. Push all changes: `git push`
4. Create PR with summary and test plan
5. Share PR URL with user

## 6. Handling Existing Work

### If Already on a Feature Branch
- Continue with commits and pushes on that branch
- Don't create a new branch unless starting a different feature

### If Working on Main
- Stash changes if needed: `git stash`
- Create branch: `git checkout -b feat/feature-name`
- Apply stash: `git stash pop`
- Commit and continue

## 7. Error Recovery

### If Commit Failed (pre-commit hooks)
- Fix the issues identified by the hooks
- Stage fixes: `git add .`
- Retry commit with same message

### If Push Failed
- Pull latest changes: `git pull --rebase`
- Resolve any conflicts
- Push again: `git push`

## Example Workflow

```bash
# 1. Start feature
git checkout main && git pull
git checkout -b feat/export-formats

# 2. Create ExportService
# ... write code ...
git add src/shared/export_service.py
git commit -m "feat: Add ExportService with JSON, CSV, Excel support"

# 3. Add CLI integration
# ... write code ...
git add run.py
git commit -m "feat: Add --format CLI flag for export format selection"
git push -u origin feat/export-formats

# 4. Add API endpoints
# ... write code ...
git add dashboard/app.py
git commit -m "feat: Add export API endpoints"

# 5. Add frontend
# ... write code ...
git add dashboard/src/
git commit -m "feat: Add export UI components"
git push

# 6. Create PR
gh pr create --title "feat: Multi-format export support" --body "..."
```
