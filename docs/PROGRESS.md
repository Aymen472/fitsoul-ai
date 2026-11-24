# Progress Log

> Update this file after every module, then commit + push.

## Current status
- [x] Planning docs written (01–04) and pushed
- [x] Module 0.1: repo skeleton, FastAPI `/health`, `uv`, `ruff`, `pytest`, `pre-commit`, `.env.example`, `.gitignore`, `README.md`
- [x] Module 0.2: GitHub Actions CI (`ruff` + `pytest`)
- [x] Module 1.1: `UserProfile` Pydantic schema, bounds/cross-field validators, BMI & high-risk flags
- [x] Module 1.2: Deterministic BMR / TDEE / calorie target & safe weekly loss calculator

## Next step
Start Module 1.3 (Macro & Condition Rules Engine) on branch `feat/macro-condition-rules`.

## Log
| Date | Module | What was built | Concepts learned |
| :--- | :--- | :--- | :--- |
| 2026-11-24 | Planning | Docs, architecture decision (hybrid app + WhatsApp notifications) | Product scoping, ADRs |
| 2026-11-24 | Module 0.1 | Backend skeleton (`backend/app/...`), FastAPI `/health`, `pydantic-settings` config, `uv` + `pyproject.toml`, `ruff`, `pytest`, `pre-commit`, `.env.example`, `.gitignore`, `README.md` | FastAPI app factory, `APIRouter`, `pydantic-settings` + `@lru_cache`, `uv` dependency groups & lockfile, Ruff lint/format, `TestClient` |
| 2026-11-25 | Module 0.2 | GitHub Actions CI workflow (`.github/workflows/ci.yml`) + CI badge in `README.md` | Continuous Integration, `uv sync --frozen`, dependency caching in GitHub Actions |
| 2026-11-25 | Module 1.1 | `UserProfile` Pydantic v2 schema (`app/models/profile.py`) with enums, timezone/date/goal validators, BMI, high-risk & supplement safety flags, unit tests (`tests/test_profile.py`), `tzdata` dependency | Pydantic v2 `StrEnum`, `@field_validator`, `@model_validator(mode="after")`, `@computed_field`, `zoneinfo` + `tzdata`, parametrized `pytest` |
| 2026-11-25 | Module 1.2 | Deterministic Mifflin-St Jeor BMR, TDEE, calorie floor (`1200`/`1500`), safe weekly loss & deadline assessor (`app/core/nutrition/calculator.py`), unit tests (`tests/test_calculator.py`) | Deterministic clinical calculations, hard safety floors, dependency-injectable `today` parameter for pure unit tests |
