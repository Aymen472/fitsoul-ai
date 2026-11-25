# Progress Log

> Update this file after every module, then commit + push.

## Current status
- [x] Planning docs written (01–04) and pushed
- [x] Module 0.1: repo skeleton, FastAPI `/health`, `uv`, `ruff`, `pytest`, `pre-commit`, `.env.example`, `.gitignore`, `README.md`
- [x] Module 0.2: GitHub Actions CI (`ruff` + `pytest`)
- [x] Module 1.1: `UserProfile` Pydantic schema, bounds/cross-field validators, BMI & high-risk flags
- [x] Module 1.2: Deterministic BMR / TDEE / calorie target & safe weekly loss calculator
- [x] Module 1.3: Config-driven macro & medical condition rules engine (PCOS, Diabetes T2, Hypertension, Hypothyroid)
- [x] Module 1.4: Curated Pakistani food CSV (165 items), fuzzy/alias search, rule-based filtering & USDA fallback client
- [x] Module 1.5: Supabase SQL schema + RLS migration, SQLAlchemy 2.0 ORM, Profile CRUD API & food seeder (Phase 1 complete!)
- [x] Module 2.1: Gemini Client Wrapper (`generate_text`, Pydantic structured output, multimodal vision, retries, cost & Langfuse tracing)
- [x] Module 2.2: AI Meal Planner, deterministic Python validator (±5%, floor, protein/carb/sodium limits), fallback & weekly grocery list
- [x] Module 2.3: Meal Photo Scanner (Gemini Vision + Pakistani Food DB / USDA matching + Roman Urdu confirmation + `MealLogRepository` + 30-meal eval)

## Next step
Start Module 2.4 (Coach Persona & Conversation Intent Router) on branch `feat/coach-persona`.

## Log
| Date | Module | What was built | Concepts learned |
| :--- | :--- | :--- | :--- |
| 2026-11-24 | Planning | Docs, architecture decision (hybrid app + WhatsApp notifications) | Product scoping, ADRs |
| 2026-11-24 | Module 0.1 | Backend skeleton (`backend/app/...`), FastAPI `/health`, `pydantic-settings` config, `uv` + `pyproject.toml`, `ruff`, `pytest`, `pre-commit`, `.env.example`, `.gitignore`, `README.md` | FastAPI app factory, `APIRouter`, `pydantic-settings` + `@lru_cache`, `uv` dependency groups & lockfile, Ruff lint/format, `TestClient` |
| 2026-11-25 | Module 0.2 | GitHub Actions CI workflow (`.github/workflows/ci.yml`) + CI badge in `README.md` | Continuous Integration, `uv sync --frozen`, dependency caching in GitHub Actions |
| 2026-11-25 | Module 1.1 | `UserProfile` Pydantic v2 schema (`app/models/profile.py`) with enums, timezone/date/goal validators, BMI, high-risk & supplement safety flags, unit tests (`tests/test_profile.py`), `tzdata` dependency | Pydantic v2 `StrEnum`, `@field_validator`, `@model_validator(mode="after")`, `@computed_field`, `zoneinfo` + `tzdata`, parametrized `pytest` |
| 2026-11-25 | Module 1.2 | Deterministic Mifflin-St Jeor BMR, TDEE, calorie floor (`1200`/`1500`), safe weekly loss & deadline assessor (`app/core/nutrition/calculator.py`), unit tests (`tests/test_calculator.py`) | Deterministic clinical calculations, hard safety floors, dependency-injectable `today` parameter for pure unit tests |
| 2026-11-25 | Module 1.3 | YAML condition rules (`app/core/rules/condition_rules.yaml`), rules engine & `NutritionTargets` (`app/core/rules/engine.py`), unit tests (`tests/test_rules_engine.py`), `pyyaml` dependency | Config-driven domain rules (YAML + Pydantic validation), multi-condition strictest-bound merging, macro-to-gram conversion |
| 2026-11-25 | Module 1.4 | Pakistani foods CSV (`data/foods/pakistani_foods.csv`), fuzzy search & rule filter (`app/core/nutrition/food_db.py`), USDA fallback client (`app/services/usda_client.py`), unit tests (`tests/test_food_db.py`) | Deterministic food scaling, multi-tier fuzzy/alias matching (`SequenceMatcher`), word-boundary allergy filtering, `httpx.MockTransport` HTTP testing |
| 2026-11-25 | Module 1.5 | Supabase SQL + RLS migration (`supabase/migrations/0001_initial_schema.sql`), SQLAlchemy 2.0 ORM (`app/db/`), Profile CRUD endpoints (`app/api/profiles.py`), food seeder (`scripts/seed_foods.py`), tests (`tests/test_profiles_api.py`) | Postgres + pgvector schema, Row-Level Security (RLS), SQLAlchemy 2.0 `Mapped` models & `session.merge`, FastAPI `Depends` + `dependency_overrides` |
| 2026-11-25 | Module 2.1 | Gemini client wrapper (`app/ai/client.py`), observability & Langfuse sink (`app/ai/tracing.py`), config updates, mocked unit tests (`tests/test_gemini_client.py`) | Gemini `responseJsonSchema`, multimodal `inlineData`, exponential backoff retries, token cost accounting, best-effort trace sinks |
| 2026-11-25 | Module 2.2 | Meal planner prompt (`app/ai/prompts/meal_planner_system.txt`), deterministic validator (`app/core/safety/meal_validator.py`), AI planner + fallback + weekly grocery list (`app/ai/meal_planner.py`), 20-profile tests (`tests/test_meal_planner.py`) | LLM-selects / Python-computes architecture, retry-with-error-feedback loop, deterministic constraint satisfaction fallback |
| 2026-11-25 | Module 2.3 | Vision prompt (`app/ai/prompts/photo_scanner_system.txt`), photo scanner (`app/ai/photo_scanner.py`), `MealLogRepository` (`app/db/repository.py`), 30-meal eval & unit tests (`tests/test_photo_scanner.py`) | Multimodal Vision → Food DB matching, low-confidence human confirmation, user edit recalculation, 30-plate evaluation dataset |
