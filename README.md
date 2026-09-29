# Rosewood Royale — AI Service

FastAPI service that answers natural-language property and rent questions for Rosewood Royale.

Laravel is the only caller in the product architecture. The Vue frontend never talks to this service directly. This service is **read-only** against Rosewood data: it calls Laravel HTTP APIs for grounding and uses LangChain + OpenAI (`ChatOpenAI`) to generate answers.

Repository: [Hsu-Hlaing-Htet/em_ai](https://github.com/Hsu-Hlaing-Htet/em_ai)

---

## Quick Start — Run Order

Start the full system in this order:

1. **MySQL** — required by Laravel
2. **Laravel Backend** — Terminal 1
3. **FastAPI AI Service** — Terminal 2 (this repository)
4. **Vue Frontend** — Terminal 3

| Terminal | Service | Typical command | Local URL |
| --- | --- | --- | --- |
| — | MySQL | Start MySQL | `127.0.0.1:3306` |
| 1 | Laravel Backend | `php artisan serve` (in `em_backend`) | http://localhost:8000 |
| 2 | FastAPI AI | `uvicorn app.main:app --reload --port 8001` | http://localhost:8001 |
| 3 | Vue Frontend | `npm run dev` (in `em_frontend`) | http://localhost:5173 |

Connection flow:

```text
Browser
   |
   v
Vue Frontend (:5173)
   |
   v
Laravel Backend (:8000)
   | \
   |  \--> FastAPI AI (:8001)
   |         |
   |         +-----> Laravel API (grounding data)
   |
   +-----> MySQL (:3306)
```

Laravel remains the authoritative business and data layer. FastAPI does not replace it.

---

## First-Time Setup

Do this once after cloning.

```bash
git clone git@github.com:Hsu-Hlaing-Htet/em_ai.git
cd em_ai
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` (placeholders only — never commit real keys):

```bash
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
BACKEND_BASE_URL=http://127.0.0.1:8000/api
```

Optional: set `AI_INTERNAL_KEY` to the same value as Laravel `AI_SERVICE_INTERNAL_KEY`.

You also need MySQL + Laravel running so grounding API calls succeed. See:

- https://github.com/Hsu-Hlaing-Htet/em_backend
- https://github.com/Hsu-Hlaing-Htet/em_frontend

Dockerfile uses **Python 3.12**. Local development typically works with a compatible Python 3.x that can install `requirements.txt`.

---

## Daily Development

1. Start MySQL
2. Start Laravel (`php artisan serve` in `em_backend`)
3. Activate venv and start this service:

```bash
cd em_ai
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

4. Start Vue (`npm run dev` in `em_frontend`) when you need the UI

Health: http://localhost:8001/health  
Interactive docs: http://localhost:8001/docs

---

## Running the Full Rosewood Royale System

### Step 1 — Database

Ensure MySQL is up and Laravel can use database `rosewood_royale`.

### Step 2 — Laravel Backend

```bash
cd em_backend
php artisan serve
```

URL: http://localhost:8000  
Laravel must set `AI_SERVICE_BASE_URL=http://127.0.0.1:8001`.

### Step 3 — FastAPI AI

```bash
cd em_ai
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

URL: http://localhost:8001

### Step 4 — Vue Frontend

```bash
cd em_frontend
npm run dev
```

URL: http://localhost:5173  
Frontend `VITE_API_BASE_URL` should be `http://localhost:8000/api`.

---

## Verify Everything Is Working

- [ ] `GET http://localhost:8001/health` → `{"status":"ok", ...}`
- [ ] Laravel is up: `GET http://localhost:8000/up`
- [ ] Via Laravel proxy (preferred product path):

```bash
curl -X POST http://localhost:8000/api/public/ai/property/ask \
  -H 'Content-Type: application/json' \
  -d '{"question": "What rentals are available?", "purpose": "rent"}'
```

- [ ] Customer rent assistant (requires a customer Sanctum token from Laravel login):

```bash
curl -X POST http://localhost:8000/api/customer/ai/rent/ask \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <laravel-token>' \
  -d '{"question": "What do I still owe?"}'
```

- [ ] In the Vue UI, public Concierge and customer rent chat return answers

Direct FastAPI calls are useful for local debugging; production traffic should go Vue → Laravel → FastAPI.

---

## Architecture

```text
Browser
   |
   v
Vue Frontend
   |
   v
Laravel Backend
   | \
   |  \--> FastAPI AI
   |
   +-----> MySQL
```

Inside this service:

```text
route → service (use case) → Laravel HTTP adapter (httpx)
                          ↓
                     LLM chain (prompt | ChatOpenAI | parser)
```

Endpoints:

| Endpoint | Purpose | Auth |
| --- | --- | --- |
| `POST /api/v1/property/ask` | Property / listing questions | Optional `X-Rosewood-AI-Internal-Key` when configured |
| `POST /api/v1/rent/ask` | Caller’s own rent/billing questions | `Authorization: Bearer <token>` forwarded to Laravel |
| `GET /health` | Health check | Public |

---

## Repository Responsibility

This AI service owns:

- FastAPI HTTP API (`/api/v1/...`, `/health`)
- Property assistant use case and prompts
- Customer rent assistant use case, privacy/out-of-scope handling, and prompts
- Context assembly from Laravel public/customer APIs
- OpenAI chat completion via LangChain

It does **not** own:

- User authentication issuance (Laravel Sanctum)
- Database writes or schema
- Invoice/payment/contract business rules
- Vue UI

Laravel remains the authoritative business and data layer.

---

## Environment Configuration

Copy `.env.example` → `.env`. Variable **names**:

### FastAPI → AI provider

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI API key (required for real answers) |
| `OPENAI_MODEL` | Model name (default `gpt-4o`) |
| `OPENAI_MAX_TOKENS` | Max tokens (default `2048`) |

### FastAPI → Laravel

| Variable | Purpose |
| --- | --- |
| `BACKEND_BASE_URL` | Laravel API base (default `http://127.0.0.1:8000/api`) |
| `BACKEND_TIMEOUT_SECONDS` | HTTP timeout for Laravel calls (default `15`) |

### Service / security

| Variable | Purpose |
| --- | --- |
| `APP_NAME` | Service name (default `rosewood-ai`) |
| `LOG_LEVEL` | Logging level |
| `AI_INTERNAL_KEY` | Optional shared secret; must match Laravel `AI_SERVICE_INTERNAL_KEY` |
| `CORS_ORIGINS` | Comma-separated origins (mainly for direct browser access; product path uses Laravel proxy) |

Never commit real API keys.

Corresponding Laravel variables: `AI_SERVICE_BASE_URL`, `AI_SERVICE_TIMEOUT_SECONDS`, `AI_SERVICE_INTERNAL_KEY`.

---

## Project Structure

```text
app/
├── main.py              # FastAPI app factory, /health, lifespan
├── api/                 # Routes, schemas, DI, internal auth middleware
│   └── v1/routes/       # property.py, rent.py
├── services/            # Property and rent use cases, privacy helpers
├── llm/                 # ChatOpenAI client, prompts, chains
├── domain/              # Models and ports
├── infrastructure/      # Laravel HTTP adapters (httpx)
└── core/                # Settings (pydantic-settings), logging
tests/                   # Unit tests (e.g. rent assistant privacy)
requirements.txt
Dockerfile
render.yaml
```

---

## Tech Stack

Confirmed from `requirements.txt` / `Dockerfile`:

- Python (Docker image: `python:3.12-slim-bookworm`)
- FastAPI `>=0.115,<1.0`
- Uvicorn `[standard] >=0.30`
- LangChain OpenAI / Core (`langchain-openai`, `langchain-core`)
- httpx, Pydantic, pydantic-settings

Default chat model from config / `.env.example`: `gpt-4o`.

---

## Common Commands

| Command | Description |
| --- | --- |
| `python3 -m venv .venv` | Create virtual environment |
| `source .venv/bin/activate` | Activate venv (Unix/macOS) |
| `pip install -r requirements.txt` | Install dependencies |
| `uvicorn app.main:app --reload --port 8001` | Start API with reload |
| `python -m pytest` | Run tests (install `pytest` if not already present) |

`pytest` is used by the existing `tests/` suite and `.pytest_cache`, but it is not listed in `requirements.txt`. Install it in the venv when you need to run tests:

```bash
pip install pytest
python -m pytest
```

---

## Testing

Unit coverage includes rent-assistant grounding/privacy behavior under `tests/test_rent_assistant.py`.

```bash
source .venv/bin/activate
pip install pytest   # if needed
python -m pytest
```

There is no separate CI test script defined in this repository beyond what you run locally.

---

## Troubleshooting

**AI unavailable from the website**  
→ Confirm this service: http://localhost:8001/health  
→ Confirm Laravel `AI_SERVICE_BASE_URL=http://127.0.0.1:8001`  
→ Confirm Laravel can reach FastAPI (no firewall / wrong host)

**401 / internal key errors**  
→ If Laravel sets `AI_SERVICE_INTERNAL_KEY`, set the same value as `AI_INTERNAL_KEY` here (or clear both for local-only work)

**Empty or failed grounding / backend errors in logs**  
→ Confirm Laravel is running  
→ Confirm `BACKEND_BASE_URL=http://127.0.0.1:8000/api`  
→ Confirm MySQL and seeded property/customer data exist

**OpenAI / model errors**  
→ Confirm `OPENAI_API_KEY` is set in `.env`  
→ Confirm network access to OpenAI from your machine

**Port 8001 in use**  
→ Stop the other process or change the uvicorn `--port` **and** update Laravel `AI_SERVICE_BASE_URL` to match

---

## Deployment

Confirmed in-repo:

- `Dockerfile` — Python 3.12, exposes port 8001, starts `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}`
- `render.yaml` — Render web service `rosewood-royale-ai`, health check `/health`, env placeholders for OpenAI and `BACKEND_BASE_URL`

Set secrets only in the platform environment. Do not commit keys.

Backend `.env.example` notes a production AI base URL shape of `https://rosewood-royale-ai.onrender.com` (no trailing slash) for Laravel `AI_SERVICE_BASE_URL`.

---

## Related Repositories

- Frontend: https://github.com/Hsu-Hlaing-Htet/em_frontend
- Backend: https://github.com/Hsu-Hlaing-Htet/em_backend
- AI: https://github.com/Hsu-Hlaing-Htet/em_ai

---

## Developer

Designed and Developed by Hsu_Hlaing-Htet

https://github.com/Hsu-Hlaing-Htet
