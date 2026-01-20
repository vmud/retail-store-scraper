# Repository Guidelines

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
