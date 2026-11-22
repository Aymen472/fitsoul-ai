# FitSoul AI — Best Practices Guide

> Yeh practices aapke kaam ko **professional, impressive aur maintainable** banayengi — chahe recruiters dekhein ya future investors/co-founders.

---

## 1. Git & GitHub Practices

### 1.1 Branching
- `main` hamesha **working** hona chahiye.
- Har feature ke liye alag branch:
  - `feat/bmr-calculator`, `feat/whatsapp-webhook`, `fix/water-reminder-timezone`, `docs/readme-setup`
- Kaam complete → **Pull Request (PR)** → khud review karo → merge. (Akeli ho tab bhi PR banao — yeh professional habit dikhata hai.)

### 1.2 Commit Messages — Conventional Commits
```
feat: add Mifflin-St Jeor BMR calculator
fix: correct calorie floor for female users
test: add PCOS rule engine tests
docs: add architecture diagram to README
refactor: extract Gemini client into ai/client.py
chore: add ruff pre-commit hook
```
- Chhote, frequent commits (din mein kam az kam 1). "final final v2" jaise messages kabhi nahi.

### 1.3 GitHub Features Use Karo
- **Issues** — har module/feature ka issue (roadmap se).
- **Projects board** — To Do / In Progress / Done (Kanban).
- **Milestones** — Phase 1, Phase 2...
- **Releases & tags** — `v0.1.0` (core engine), `v0.2.0` (AI brain)...
- **GitHub Actions** — CI (lint + tests) har push par.

### 1.4 Kabhi Push Mat Karna ⚠️
- `.env` file, API keys, WhatsApp tokens, database passwords.
- User data, real photos.
- `.env.example` push karo (sirf variable names, values nahi).
- Agar ghalti se key push ho jaye → foran key **revoke/rotate** karo (history se delete karna kaafi nahi).

---

## 2. Code Quality

| Practice | Tool |
| :--- | :--- |
| Formatting + linting | `ruff` |
| Type hints | Python type hints + `mypy` (optional) |
| Data validation | Pydantic |
| Pre-commit checks | `pre-commit` |
| Frontend lint | ESLint + Prettier |

- Functions chhote aur ek kaam wale.
- Magic numbers nahi — constants/config file mein (e.g. `FEMALE_CALORIE_FLOOR = 1200`).
- Business logic (nutrition) ko AI aur API code se **alag** rakho.

---

## 3. Testing
- **Unit tests** — nutrition calculator, rules engine, validators (yeh 100% tested hone chahiye — health data hai!).
- **AI evaluation set** — 30–50 test profiles + 30 meal photos; har prompt change ke baad results compare karo.
- **Safety red-team tests** — tricky/dangerous prompts ki file.
- Target: core modules par **80%+ coverage** (`pytest --cov`).

---

## 4. AI-Specific Best Practices
1. **Numbers kabhi AI se nahi** — calories/macros hamesha code + database se.
2. **Structured outputs** — Pydantic schema; free text parse mat karo.
3. **Prompts version control mein** — `ai/prompts/` folder mein files, code mein hard-coded nahi.
4. **Observability** — Langfuse se har call ka cost, latency, input/output trace.
5. **Cost control** — sasta model (Flash) default; caching; message history trim.
6. **Fallbacks** — AI fail ho to graceful message + retry.

---

## 5. Security & Privacy
- Secrets sirf `.env` / hosting dashboard mein.
- WhatsApp webhook signature verify karo.
- Supabase Row-Level Security — har user sirf apna data dekhe.
- Photos private buckets mein, signed URLs.
- Logs mein personal health data mask karo.

---

## 6. Documentation (Impressive Banane Ka Raaz)
### README.md mein hona chahiye:
1. Project name + one-line pitch + badges (CI status, license)
2. Demo GIF / screenshots / live link
3. Features list
4. Architecture diagram (Mermaid)
5. Tech stack
6. Setup instructions (local run in 5 steps)
7. Roadmap (checkboxes)
8. Medical disclaimer

### Aur:
- `docs/` folder mein yeh documents.
- **ADRs (Architecture Decision Records)** — `docs/decisions/001-why-whatsapp-first.md` — har bara decision kyun liya. Senior engineers yeh dekh kar bohat impress hote hain.
- `CHANGELOG.md` releases ke sath.

---

## 7. Building in Public (Personal Brand + Marketing)
- LinkedIn / X par har hafte progress post: "Week 3: Built an AI that reads desi meal photos 🍛".
- Short demo videos.
- Yeh ek sath **CV, marketing aur early users** teeno deta hai.

---

## 8. Product Practices
- Pehle **MVP** — perfect mat banao, jaldi real users tak pohnchao.
- Har hafte kam az kam 3 users se baat karo.
- Metrics track karo: retention, daily logging, trial → paid.
- Feature tab add karo jab users maangein, sirf apne andaze par nahi.

---

## 9. AI Agent (Antigravity) Ke Sath Kaam Karne Ki Practices
- Project root mein `GEMINI.md` rakho (project rules, tech stack, coding style) — har nayi chat mein agent automatically follow karega.
- Bara kaam ho to `/plan` command se pehle plan banwao.
- Agent ka likha code **samjho** — har module ke baad poocho "yeh kaise kaam karta hai?" (learning ka asli faida yahin hai).
- Kaam ke progress ke liye `docs/PROGRESS.md` update karte raho.

---

## 10. Daily Checklist ✅
- [ ] Branch banai
- [ ] Code + tests likhe
- [ ] `ruff` + `pytest` pass
- [ ] Meaningful commit message
- [ ] Push + PR
- [ ] Issue/board update
- [ ] Kuch naya seekha? `PROGRESS.md` mein note
