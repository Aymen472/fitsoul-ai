# Architecture Decisions

## ADR-001: Hybrid channel strategy (FINAL — overrides earlier "WhatsApp-first" wording)

**Decision:** The main experience lives in **our own web app (Next.js PWA)**. WhatsApp is used **only for notifications** (reminders, check-ins, payment reminders) via the official Meta WhatsApp Cloud API with approved templates. Each notification contains a deep link that opens the app.

**What the app contains:**
- AI chat with the **full persistent history** (stored in Supabase Postgres, visible on any device)
- Dashboard: calories, macros, water, streaks, weight graphs, meal history with photos
- Workout player + face yoga, weekly meal plan, grocery list
- Subscription / billing

**Optional later:** user can send a meal photo directly to the WhatsApp number; backend logs it into the same history.

**Why:**
- We own the chat history and data.
- Lower WhatsApp cost (only template notifications are sent).
- Dashboard, graphs and workout timers do not work well inside WhatsApp.

**Notifications:** WhatsApp templates + web push (PWA). Compare which channel retains better.

**Steps tracking:** A PWA cannot read the phone step counter. Steps need a native mobile app (Android Health Connect / Google Fit, Apple Health). Until then: manual entry. Native app = later phase.

## Updated build order
1. Phase 0: repo setup, FastAPI `/health`, CI
2. Phase 1: nutrition engine, food DB, profile
3. Phase 2: AI brain (meal planner + validator, photo scanner, safety, coach persona)
4. Phase 3: **Web app first** (auth, chat with history, dashboard, workout player)
5. Phase 4: **WhatsApp notifications** (webhook, templates, scheduler)
6. Phase 5: payments, admin, beta
7. Phase 6: native mobile app (steps tracking), scale

(`02_DEVELOPMENT_ROADMAP.md` still shows Phase 3 = WhatsApp and Phase 4 = Web app. This file takes priority; swap them when you reach those phases.)
