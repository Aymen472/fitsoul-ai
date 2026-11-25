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
- [x] Module 2.5: Safety Guardrails (input/output crisis, ED, medicine & crash-diet checks), whitelist-only supplements & 56 red-team tests
- [x] Module 2.4: Coach Persona, deterministic intent router (10 intents), chat text meal parser & safety-wrapped `CoachAgent`
- [x] Module 2.6: Long-term memory (`pgvector` migration + semantic retrieval), emotional pattern detector & live `/api/v1/chat` + `/api/v1/meal-plans` REST APIs (Phase 2 complete!)
- [x] Module 3.1: Next.js 15 PWA setup (manifest, icons, service worker), Tailwind v4 UI shell, hybrid Auth (Supabase + local dev), live Health Onboarding wired to FastAPI + CORS & Frontend CI
- [x] Module 3.2: Live AI Coach Chat UI with persistent history, quick prompts, safety/care alerts & long-term memory/pattern insights (`GET /api/v1/chat/{user_id}/memories`)

## Next step
Start Phase 3 — Module 3.3 (Dashboard: Calorie Ring, Macros, Water/Weight/Mood Tracking & Meal History) on branch `feat/pwa-dashboard`.

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
| 2026-11-25 | Module 2.5 | Input/output guardrails (`app/core/safety/guardrails.py`), whitelist-only supplements (`app/core/safety/supplements.py`), 56 red-team + safety tests (`tests/test_safety_guardrails.py`) | Defense-in-depth safety screening, English + Roman Urdu crisis/ED patterns, context-scoped calorie floor checks, high-risk lockout |
| 2026-11-25 | Module 2.4 | Coach prompt (`app/ai/prompts/coach_system.txt`), intent router + text meal parser (`app/ai/intent_router.py`), safety-wrapped `CoachAgent` (`app/ai/coach.py`), tests (`tests/test_coach_agent.py`) | Deterministic intent routing, natural-language meal parsing → Food DB math, safety-first pre/post LLM wrapping |
| 2026-11-25 | Module 2.6 | `user_memories` pgvector migration (`0002_user_memories.sql`) + ORM (`app/db/tables.py`), chat/memory/mood repositories (`app/db/repository.py`), deterministic embeddings, semantic retrieval & pattern detector (`app/ai/memory.py`), live `/api/v1/chat` & `/api/v1/meal-plans` APIs (`app/api/chat.py`), tests (`tests/test_memory_and_chat_api.py`) | Semantic memory retrieval (`cosine_similarity` + `pgvector`), bilingual fact extraction, behavioral pattern detection & proactive nudges, end-to-end FastAPI persistence |
| 2026-11-25 | Module 3.1 | Next.js 15 PWA shell (`frontend/src/app/`, `manifest.ts`, `sw.js`, SVG icons), hybrid auth (`Supabase` + local dev), live Health Onboarding wired to FastAPI + CORS (`app/config.py`, `app/main.py`), Vitest tests & frontend CI job (`.github/workflows/ci.yml`) | Next.js App Router PWA fundamentals, Tailwind v4 tokens, FastAPI `CORSMiddleware`, hybrid auth state management, typed REST error handling |
| 2026-11-25 | Module 3.2 | `GET /api/v1/chat/{user_id}/memories` (`app/api/chat.py`), chat helpers & tests (`chat-helpers.ts`), live `/chat` workspace (`ChatMessageBubble.tsx`, `CoachInsightsPanel.tsx`, `app/chat/page.tsx`) | Optimistic UI chat flow, `Promise.allSettled` workspace hydration, memory/pattern badges, safety care banners |
