# FitSoul AI — Project Instructions for AI Agents

## Project
FitSoul AI: AI nutritionist + fitness coach + emotional support companion, delivered via WhatsApp (primary) and a Next.js PWA. Target: Pakistani / South Asian users (PCOS, diabetes, weight loss, brides/grooms, busy professionals).

Full specs: `docs/01_PROJECT_OVERVIEW.md`, roadmap: `docs/02_DEVELOPMENT_ROADMAP.md`, practices: `docs/03_BEST_PRACTICES.md`.

## Communication
- The developer is learning AI engineering. Explain decisions and new concepts briefly in Roman Urdu + English technical terms.
- After finishing a module, summarize what was built and what concepts were used.

## Tech Stack
- Backend: Python 3.12, FastAPI, Pydantic, Supabase (Postgres + pgvector), Gemini API.
- Frontend: Next.js, TypeScript, Tailwind, shadcn/ui.
- Tooling: ruff, pytest, pre-commit, GitHub Actions, Docker.

## Non-negotiable Rules
1. Calories, macros, BMR/TDEE are ALWAYS computed by deterministic Python code and the food database — never invented by the LLM.
2. Enforce calorie floors (female ≥ 1200, male ≥ 1500 kcal) and condition rules (PCOS, diabetes, hypertension).
3. Never suggest prescription medicines or dosages. Supplements: whitelist only, with a doctor-confirmation note; disabled for high-risk users.
4. Detect eating-disorder / self-harm signals and respond safely (stop diet advice, suggest professional help).
5. Never commit secrets; use `.env` and keep `.env.example` updated.
6. Every new core function needs unit tests.
7. Use Conventional Commits and feature branches.
