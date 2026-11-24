# Progress Log

> Update this file after every module, then commit + push.

## Current status
- [x] Planning docs written (01–04) and pushed
- [x] Module 0.1: repo skeleton, FastAPI `/health`, `uv`, `ruff`, `pytest`, `pre-commit`, `.env.example`, `.gitignore`, `README.md`
- [x] Module 0.2: GitHub Actions CI (`ruff` + `pytest`)

## Next step
Verify CI green on GitHub, merge `feat/project-setup` PR into `main`, then start Phase 1 — Module 1.1 (`UserProfile` Pydantic schema) on `feat/user-profile-schema`.

## Log
| Date | Module | What was built | Concepts learned |
| :--- | :--- | :--- | :--- |
| 2026-11-24 | Planning | Docs, architecture decision (hybrid app + WhatsApp notifications) | Product scoping, ADRs |
| 2026-11-24 | Module 0.1 | Backend skeleton (`backend/app/...`), FastAPI `/health`, `pydantic-settings` config, `uv` + `pyproject.toml`, `ruff`, `pytest`, `pre-commit`, `.env.example`, `.gitignore`, `README.md` | FastAPI app factory, `APIRouter`, `pydantic-settings` + `@lru_cache`, `uv` dependency groups & lockfile, Ruff lint/format, `TestClient` |
| 2026-11-25 | Module 0.2 | GitHub Actions CI workflow (`.github/workflows/ci.yml`) + CI badge in `README.md` | Continuous Integration, `uv sync --frozen`, dependency caching in GitHub Actions |
