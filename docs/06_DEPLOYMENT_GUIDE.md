# FitSoul AI Production Deployment Guide

Complete checklist to take FitSoul AI from local development to beta/public launch using **Supabase**, **Render**, **Vercel**, and **Meta WhatsApp Cloud API**.

---

## 1. Supabase Postgres + `pgvector` Setup

1. Create a new Supabase project and open the **SQL Editor**.
2. Run the four migrations in exact order:
   - `supabase/migrations/0001_initial_schema.sql` (core tables, indexes, RLS)
   - `supabase/migrations/0002_user_memories.sql` (semantic long-term memory table)
   - `supabase/migrations/0003_whatsapp_notifications.sql` (preferences + notification delivery logs)
   - `supabase/migrations/0004_payment_transactions.sql` (checkout orders + webhook ledger)
3. Enable Email/Phone OTP auth under **Authentication → Providers**, and copy:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `DATABASE_URL` (Postgres connection string with `?sslmode=require`)
4. Seed the 165 curated Pakistani foods into Postgres (or call `GET /api/v1/admin/foods` once from `/admin`):
   ```bash
   cd backend
   DATABASE_URL="postgresql://..." uv run python scripts/seed_foods.py
   ```

---

## 2. Local Container Verification (`docker compose`)

Before cloud deployment, verify both production Docker images locally from the repository root:

```bash
docker compose up --build
```

- FastAPI Backend: `http://127.0.0.1:8000/health` → `{"status":"ok"}`
- Readiness Probe: `http://127.0.0.1:8000/health/ready` → verifies DB + 165 foods + safe boolean integration flags
- Next.js PWA: `http://localhost:3000/welcome` (Public Landing Page) and `http://localhost:3000/` (App Hub)

---

## 3. Backend & Hourly Scheduler on Render (`render.yaml`)

1. Connect your GitHub repository in Render → **New Blueprint** (`render.yaml`).
2. Render creates:
   - **`fitsoul-ai-api`** (Docker web service using `backend/Dockerfile`)
   - **`fitsoul-ai-scheduler`** (Hourly cron job calling `POST /api/v1/notifications/scheduler/run`)
3. Fill all `sync: false` secrets in Render's Environment tab:
   - `CORS_ORIGINS`: your Vercel domain, e.g. `https://app.fitsoul.pk`
   - `PWA_BASE_URL`: `https://app.fitsoul.pk`
   - `GEMINI_API_KEY`: Google AI Studio key
   - `ADMIN_API_KEY`: strong random token (required because `APP_ENV=production` fails closed on admin routes)
   - `SCHEDULER_SECRET`: strong random token shared between `fitsoul-ai-api` and `fitsoul-ai-scheduler`
   - `PAYMENT_WEBHOOK_SECRET`: strong HMAC secret shared with Safepay / PayFast / LemonSqueezy
   - `WHATSAPP_*`: Meta Business app token, verify token, phone number ID, and app secret

---

## 4. Frontend PWA on Vercel

1. Import the GitHub repository in Vercel and set **Root Directory** to `frontend`.
2. Add Environment Variables:
   - `NEXT_PUBLIC_API_URL=https://fitsoul-ai-api.onrender.com` (no trailing slash)
   - `NEXT_PUBLIC_SUPABASE_URL=<your Supabase URL>`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY=<your Supabase anon key>`
3. Deploy and verify installable PWA manifest at `https://app.fitsoul.pk/manifest.webmanifest` and landing page at `/welcome`.

---

## 5. Meta WhatsApp & Payment Gateways Webhook Setup

- **Meta WhatsApp Cloud API:**
  - Callback URL: `https://<your-api-domain>/webhooks/whatsapp`
  - Verify Token: must match `WHATSAPP_VERIFY_TOKEN`
  - Subscribe to `messages` webhook field (signed via `WHATSAPP_APP_SECRET`).
- **Payment Gateways (Safepay / PayFast / JazzCash / Easypaisa / LemonSqueezy):**
  - Webhook URL: `https://<your-api-domain>/webhooks/payments/{provider}`
  - Signature Header: `X-Payment-Signature` HMAC-SHA256 using `PAYMENT_WEBHOOK_SECRET`.

---

## 6. Pre-Launch Checklist

- [ ] `GET /health/ready` returns `status: "ready"`, `database_ok: true`, and `food_catalog_count >= 165`.
- [ ] `ADMIN_API_KEY` is non-empty in production and `/admin` prompts cleanly for `X-Admin-Key`.
- [ ] `CORS_ORIGINS` strictly lists your production frontend origin (not wildcard `*`).
- [ ] WhatsApp `STOP` / `START` opt-out and general `/chat` redirect tested end-to-end.
- [ ] Payment webhook idempotency verified (`payment.succeeded` updates subscription once).
- [ ] Self-service `/legal` privacy disclaimer and `DELETE /api/v1/profiles/{user_id}/data` verified.
