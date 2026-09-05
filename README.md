# RecoverAI — Autonomous Revenue Recovery Agent

Detect → Diagnose → Decide → Act → Recover → Audit

Bounded, compliant revenue recovery agent for Razorpay test mode. Hybrid intelligence: sklearn Recovery Score + deterministic policy engine + structured AI reasoning logs. Mock executor works without API keys.

## Stack

- **Backend:** FastAPI, SQLAlchemy, SQLite, scikit-learn
- **Frontend:** React + Vite
- **Payments:** Razorpay Test APIs (or deterministic mock)

## Quick start

### 1. Backend

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

API docs: http://127.0.0.1:8000/docs

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Control Center: http://127.0.0.1:5173

### 3. Optional Razorpay test keys

Edit `backend/.env`:

```
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
```

If unset, the agent uses the **mock** executor (stable demo KPIs).

## Demo script (judges, ~30 seconds)

1. Open **Control Center** — show Revenue At Risk.
2. Click **Run Agent** — agent processes open cases.
3. Switch to **Audit Trail** — Time / Customer / Problem / AI Decision / Action / Result.
4. Open **Policy / Bounds** — max 2 retries, max 3 attempts → STOP, amount > ₹25,000 → escalate, no duplicates.
5. Return to Control Center — Recovery Rate + AI Actions breakdown.

Reset anytime with **Reset Demo Data**.

## Agent loop

| Step | What happens |
|------|----------------|
| Detect | Load open / in-progress cases, priority by Recovery Score |
| Diagnose | Failure reason, temporary vs hard, severity |
| Decide | Policy maps diagnosis → retry / link / reminder / mandate / escalate / stop |
| Bounds | Enforce attempt caps, amount approval, idempotency |
| Act | Razorpay test API or mock |
| Verify | Map provider result → recovered / in progress / stopped |
| Audit | Append immutable audit row |

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/dashboard` | KPIs + action counts |
| GET | `/api/cases` | Cases (filter `status`, `problem_type`) |
| GET | `/api/audit` | Audit trail |
| POST | `/api/agent/run` | Run batch recovery agent |
| POST | `/api/cases/{id}/recover` | Recover one case |
| POST | `/api/seed` | Reseed synthetic demo data |
| GET | `/api/policy` | Stopping rules for UI |

## Policy bounds (bar)

- Maximum automatic retries: **2**
- Maximum recovery attempts: **3** → then **STOP**
- Amount requiring human approval: **> ₹25,000**
- No duplicate payment action (idempotency key per case+action+attempt)

## Project layout

```
backend/app/
  agent/          # diagnose, decide, act, verify, loop
  ml/             # Recovery Score model
  api/routes.py
  seed.py
  main.py
frontend/src/
  App.tsx         # Control Center UI
  api.ts
```
