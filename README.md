# Rosewood AI

AI service for **Rosewood Royale**. A FastAPI app that answers natural-language
questions, grounded in the Laravel backend data, using **LangChain** +
**`langchain-openai`** (`ChatOpenAI`, model `gpt-4o`).

The Vue frontend calls **Laravel proxy routes** only; Laravel forwards requests
to this service. Do not expose this service directly to browsers in production.

It exposes **two endpoints**:

| Endpoint | Purpose | Auth |
|---|---|---|
| `POST /api/v1/property/ask` | Information about a property (or a search across listings) | Optional internal key from Laravel |
| `POST /api/v1/rent/ask` | The caller's own rent information (invoices, payments, ...) | `Authorization: Bearer <token>` (forwarded to Laravel) |

This service is **read-only** — it calls the backend HTTP API and never writes
to the Rosewood database.

## Architecture

Ports-and-adapters (hexagonal) layering — dependencies point inward, so the LLM
and HTTP details stay at the edges:

```
app/
  api/            HTTP layer — routes, request/response schemas, DI wiring (deps.py)
  services/       Use cases — orchestrate a data source + an LLM chain
  llm/            ChatOpenAI factory, prompts, and the grounded chains
  domain/         Entities (models.py) + ports/interfaces (ports.py)
  infrastructure/ Adapters that implement the ports against the Laravel API
  core/           Config (pydantic-settings) and logging
  main.py         App factory + lifespan (shared httpx client)
```

Request flow:

```
route → service (use case) → DataSource port → backend adapter (httpx) → Laravel API
                          ↓
                     LLM chain (prompt | ChatOpenAI | parser)
```

## Grounding

Both prompts (`app/llm/prompts.py`) pin the model to the JSON `CONTEXT`
assembled from backend data and forbid invented prices, dates, or statuses.

Laravel endpoints used for grounding:

- `GET /api/public/properties` (optional `search`, `purpose=rent|sale`)
- `GET /api/customer/dashboard`, `/contracts`, `/invoices`, `/payments` (with user Bearer token)

## Run

```bash
cd ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set OPENAI_API_KEY and BACKEND_BASE_URL
uvicorn app.main:app --reload --port 8001
```

Interactive docs at <http://localhost:8001/docs>.

## Examples

```bash
# Property question (via Laravel proxy in production)
curl -X POST http://localhost:8000/api/public/ai/property/ask \
  -H 'Content-Type: application/json' \
  -d '{"question": "What rentals are available?", "purpose": "rent"}'

# Rent question (customer Sanctum token)
curl -X POST http://localhost:8000/api/customer/ai/rent/ask \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <user-backend-token>' \
  -d '{"question": "How much do I still owe and what is overdue?"}'
```

## Configuration

See `.env.example`. Key variables: `OPENAI_API_KEY`, `OPENAI_MODEL`
(default `gpt-4o`), `BACKEND_BASE_URL` (default
`http://127.0.0.1:8000/api`), optional `AI_INTERNAL_KEY` (must match
`AI_SERVICE_INTERNAL_KEY` in Laravel when set).
