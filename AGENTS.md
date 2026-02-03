# Repository Guidelines

## Multi-Agent Development

This repository supports parallel development by multiple AI coding agents (Claude Code, Cursor, Copilot, Gemini, Aider). Follow these rules to prevent conflicts.

### Core Rule: Worktree Isolation

Every agent works in its own git worktree. Never work directly in the main repository clone.

```bash
# Create your worktree
cd ~/dev/projects/retail-store-scraper
git checkout main && git pull
git worktree add ../retail-store-scraper--{type}-{agent}-{task} -b {type}/{agent}-{task}
cd ../retail-store-scraper--{type}-{agent}-{task}
```

### Agent IDs

| Agent | ID | Branch Example |
|-------|-----|----------------|
| Claude Code | `cc1`, `cc2` | `feat/cc1-export` |
| Cursor | `cursor` | `fix/cursor-bug` |
| GitHub Copilot | `copilot` | `refactor/copilot-utils` |
| Google Gemini | `gemini` | `feat/gemini-feature` |
| Aider | `aider` | `fix/aider-issue` |
| Human | `human` | `feat/human-task` |

### Commit Format

```
{type}: {description}

Agent: {agent-id}
```

### High-Conflict Files

Check if another agent is editing before modifying:
- `run.py` - main entry point
- `config/retailers.yaml` - shared configuration
- `CLAUDE.md` / `AGENTS.md` - project instructions
- `requirements.txt` - dependencies

### Tool-Specific Instructions

- **Claude Code**: `.claude/rules/devops-workflow.md` (comprehensive)
- **Cursor**: `.cursorrules`
- **GitHub Copilot**: `.github/copilot-instructions.md`

---

## Project Structure & Module Organization

- `src/`: Core scraper code and shared utilities (e.g., `src/shared/`, `src/scrapers/`).
- `dashboard/`: Flask dashboard API and UI assets (`dashboard/app.py`, `dashboard/static/`, `dashboard/templates/`).
- `tests/`: Pytest suite, including scraper-specific tests under `tests/test_scrapers/`.
- `config/retailers.yaml`: Primary configuration for retailers, proxy settings, and defaults.
- `data/`: Runtime outputs (logs, checkpoints, exports) per retailer, e.g., `data/verizon/output/`.

## Build, Test, and Development Commands

- `venv/bin/python run.py --retailer verizon`: Run a single scraper with the CLI.
- `venv/bin/python run.py --all --exclude bestbuy`: Run all enabled scrapers except selected ones.
- `venv/bin/python -m pytest -q`: Run the full test suite.
- `venv/bin/python -m pytest tests/test_scrapers/test_verizon.py -q`: Run a targeted test file.
- `venv/bin/python dashboard/app.py`: Start the Flask dashboard (uses `.env` if present).

## Coding Style & Naming Conventions

- Python code uses 4-space indentation and `snake_case` for functions/variables.
- Classes use `CamelCase`; constants use `UPPER_SNAKE_CASE`.
- Prefer explicit types in dataclasses and function signatures where practical.
- Keep utilities in `src/shared/` and scraper logic in `src/scrapers/<retailer>.py`.

## Testing Guidelines

- Framework: `pytest`.
- Place new tests in `tests/` with `test_*.py` naming.
- Use focused tests for scraper logic under `tests/test_scrapers/`.
- Ensure config validation and export sanitization behaviors are covered.

## Commit & Pull Request Guidelines

- Commit messages follow conventional prefixes (e.g., `fix: ...`, `feat: ...`, `docs: ...`).
- PRs should include a clear description, linked issues when applicable, and a brief test plan.
- For UI or dashboard changes, include screenshots or a short screencast.

## Security & Configuration Tips

- Set `FLASK_SECRET_KEY` for production; otherwise `.flask_secret` is generated locally.
- Proxy credentials are read from environment variables; validate with `--validate-proxy`.
- Avoid committing secrets or generated data under `data/`.
