# Rosewood Royale — AI Service

FastAPI service for natural-language property discovery and customer rent/billing questions. It assembles context from Laravel data and uses LangChain with OpenAI when configured, with deterministic fallback answers when the model is unavailable. It reads application data through HTTP APIs and does not connect to MySQL or write business records.

The product request path is browser → Vue → Laravel → FastAPI. Laravel owns authentication, authorization, and business rules; the browser never receives an OpenAI key or calls FastAPI directly.

Repository: [em_ai](https://github.com/Hsu-Hlaing-Htet/em_ai).

## Technology Stack

- Python; the included Docker runtime uses Python 3.12.
- FastAPI `>=0.115,<1.0` and Uvicorn for HTTP serving.
- LangChain OpenAI/Core, httpx, Pydantic 2, and pydantic-settings.
- pytest for the current offline rent-assistant tests (installed separately).

[requirements.txt](requirements.txt) defines dependency ranges, not a fully pinned lockfile. Model defaults and environment loading are defined in [app/core/config.py](app/core/config.py).

## Prerequisites

- Python **3.12** for parity with the Dockerfile, including `venv` and pip. No local Python version range is declared; do not assume an arbitrary system Python is supported.
- Git. The examples use macOS/Linux shell syntax; a PowerShell activation command is included below.
- The [Laravel backend](https://github.com/Hsu-Hlaing-Htet/em_backend#readme), configured with MySQL, migrated, seeded, and running on port `8000`, for real application data.
- Optional OpenAI API credentials and network access for provider-backed answers. They are not needed for startup, `/health`, deterministic fallback answers, or offline tests.

Start MySQL → backend → AI → frontend. This service needs no database driver, migration, or queue worker of its own.

## Quick Start

From this repository's root with Python 3.12 installed and Laravel running:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

The template's `BACKEND_BASE_URL=http://127.0.0.1:8000/api` matches the local backend. Leave `OPENAI_API_KEY` empty for fallback mode, or configure it privately for model-generated answers. Match any internal key configured on Laravel before testing the proxy.

In another terminal:

```bash
curl --fail http://127.0.0.1:8001/health
```

Expect `{"status":"ok","service":"rosewood-ai"}` with the default service name. `/health` confirms the service is running; it does not check Laravel, MySQL, or OpenAI. Use the request under [Verification](#verification) to exercise the application path.

## Detailed Local Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/Hsu-Hlaing-Htet/em_ai.git
cd em_ai
python3.12 --version
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Skip steps already completed in Quick Start. Keep the virtual environment local and use `python -m pip` so packages install into the interpreter you activated.

On Windows PowerShell with Python 3.12 installed, use:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### 2. Configure Laravel connectivity

Set the AI `.env`:

```dotenv
BACKEND_BASE_URL=http://127.0.0.1:8000/api
BACKEND_TIMEOUT_SECONDS=15
```

In the backend `.env`, confirm:

```dotenv
AI_SERVICE_BASE_URL=http://127.0.0.1:8001
AI_SERVICE_TIMEOUT_SECONDS=60
```

The AI's Laravel URL **includes `/api`**; Laravel's AI URL has **no `/api` suffix**. If using the internal gate, generate a private shared value and configure it as `AI_INTERNAL_KEY` here and `AI_SERVICE_INTERNAL_KEY` in Laravel. Do not put it in the frontend.

Laravel preloads property/customer context for proxied requests, avoiding a callback into a single-worker local Laravel server. Direct FastAPI requests without preloaded context fetch Laravel APIs themselves. Customer requests forward the Bearer token so Laravel controls data access.

### 3. Choose fallback or provider-backed answers

Leaving `OPENAI_API_KEY` empty disables model-chain construction; the service still formats answers from grounded data. For provider-backed generation, set your private key in `.env` and use a model available to that account. `OPENAI_MODEL=gpt-4o` is the repository default, not a guarantee of account access.

The service also falls back when a model invocation fails. A successful answer alone does not establish that OpenAI was used; check service logs when verifying provider connectivity. The response's `model` field names the configured model even when fallback formatting supplied the answer. Restart Uvicorn after environment changes because settings and the model factory are cached.

## Environment Configuration

Use [.env.example](.env.example) as the template. Settings load from the environment and a `.env` in the current working directory, so launch from the repository root. Exported environment variables override `.env` values.

| Variable | Default / behavior |
| --- | --- |
| `OPENAI_API_KEY` | Empty; optional for fallback mode, required for provider-backed generation. |
| `OPENAI_MODEL` | `gpt-4o`; model identifier sent to the configured provider. |
| `OPENAI_MAX_TOKENS` | `2048`; model output-token limit. |
| `BACKEND_BASE_URL` | `http://127.0.0.1:8000/api`; Laravel data API. |
| `BACKEND_TIMEOUT_SECONDS` | `15`; timeout for HTTP requests to Laravel. |
| `APP_NAME` | `rosewood-ai`; service name in health output and logs. |
| `LOG_LEVEL` | `INFO`. |
| `AI_INTERNAL_KEY` | Empty; when set, protected requests need `X-Rosewood-AI-Internal-Key` with the matching value. |
| `CORS_ORIGINS` | Comma-separated origins. The example file lists `http://localhost:5173,http://localhost:8080`; code defaults also include other local development origins when the variable is absent. Product traffic uses Laravel, so direct browser access is unnecessary. |

Do not commit `.env`, API keys, customer tokens, or internal secrets. CORS does not authenticate server-to-server requests. Configure the internal gate and appropriate network restrictions when exposing this service beyond local development; the preloaded context fields are intended for the trusted Laravel proxy.

## Running the Application

Activate the virtual environment in each new terminal, then run:

```bash
source .venv/bin/activate
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

- [Health](http://127.0.0.1:8001/health)
- [Interactive API docs](http://127.0.0.1:8001/docs)
- [OpenAPI schema](http://127.0.0.1:8001/openapi.json)

### API surface

| Method and path | Purpose | Requirements |
| --- | --- | --- |
| `GET /health` | Process/service health | Public, even when the internal gate is enabled. |
| `POST /api/v1/property/ask` | Property listing questions | Internal header when `AI_INTERNAL_KEY` is set. |
| `POST /api/v1/rent/ask` | Customer rent/billing questions | Bearer token, plus the internal header when configured. |

The internal gate also exempts `/docs`, `/openapi.json`, and `/redoc`. Direct requests to protected endpoints from the docs still need the internal header when the gate is enabled. Request/response models are in [app/api/schemas.py](app/api/schemas.py).

### Verification

With Laravel and this service running, exercise the preferred product path:

```bash
curl --fail -X POST http://127.0.0.1:8000/api/public/ai/property/ask \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{"question":"What rentals are available?","purpose":"rent"}'
```

Expect an HTTP 200 response with `data.answer` and `data.properties` in Laravel's response envelope. An empty listing result can be valid; check seeded/available inventory rather than assuming transport failure.

For customer grounding, replace the token placeholder with a local **customer** Sanctum token obtained through Laravel login:

```bash
curl --fail -X POST http://127.0.0.1:8000/api/customer/ai/rent/ask \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <customer-token>' \
  -d '{"question":"What do I still owe?"}'
```

Confirm the response concerns that customer's own billing data. These proxy requests need no internal header from the client: Laravel adds its server-side key. Keep tokens private, including in shell history. Finally, verify the public/customer chat interfaces in the frontend if testing the complete system.

## Running Tests

Install pytest separately because it is not listed in the runtime requirements:

```bash
source .venv/bin/activate
python -m pip install pytest
OPENAI_API_KEY= python -m pytest
```

For PowerShell, set the empty key inside the Python process so it also overrides any `.env` value:

```powershell
python -c "import os, pytest; os.environ['OPENAI_API_KEY'] = ''; raise SystemExit(pytest.main())"
```

[tests/test_rent_assistant.py](tests/test_rent_assistant.py) uses fake rent data and forces the deterministic answer path. Clearing the key prevents construction of a provider client while running these tests. No Laravel server, MySQL database, OpenAI network access, or customer token is required. Coverage includes privacy/out-of-scope handling, preloaded context, missing data, and contract/invoice fallback answers. It does not establish live property retrieval or provider integration. No separate CI test workflow is defined in this repository.

## Project Structure

```text
app/main.py              FastAPI application, lifespan, health endpoint
app/api/                 Schemas, dependencies, internal-key middleware
app/api/v1/routes/       Property and rent HTTP endpoints
app/services/            Context assembly, use cases, privacy/fallback behavior
app/llm/                 Model factory, prompts, and LangChain runnables
app/domain/              Models and data-source interfaces
app/infrastructure/      Laravel HTTP adapters
app/core/                Environment settings and logging
tests/                   Offline rent-assistant tests
requirements.txt         Runtime dependency ranges
Dockerfile               Python 3.12 container runtime
render.yaml              Render service configuration
```

## Troubleshooting

| Symptom | Check or resolution |
| --- | --- |
| Import error / package missing | Activate `.venv`, confirm `python --version`, and run `python -m pip install -r requirements.txt` from the root. |
| `.env` changes have no effect | Start from the repository root, check exported overrides, and restart Uvicorn; settings/model factories are cached. |
| Health works but chat fails | Health checks no dependencies. Test Laravel `/up` and the proxy request above; inspect both service logs. |
| Protected FastAPI request returns 403 | Supply the internal header for direct debugging, or match AI `AI_INTERNAL_KEY` with backend `AI_SERVICE_INTERNAL_KEY` for the proxy. |
| Customer request returns 401 / 403 | Obtain a valid customer Bearer token from Laravel; confirm the account's role and authorization. |
| Grounding request fails / returns 502 | Check `BACKEND_BASE_URL` includes `/api`, Laravel/MySQL availability, and the customer's accessible data. |
| Answer uses fallback unexpectedly | Check whether the key is empty and inspect warnings about model invocation failures, credentials, account model access, or network/timeouts. |
| Port 8001 is occupied | Stop the conflicting process or change Uvicorn's port and Laravel's `AI_SERVICE_BASE_URL` together. |
| pytest is missing | Install it explicitly in the active virtual environment; it is not a runtime dependency. |

## Deployment Notes

[Dockerfile](Dockerfile) builds a Python 3.12 image and starts Uvicorn on `0.0.0.0:${PORT:-8001}` without reload. [render.yaml](render.yaml) configures `/health` and the service environment. Build locally with:

```bash
docker build -t rosewood-ai .
docker run --rm -p 8001:8001 --env-file .env rosewood-ai
```

Before running a container, set `BACKEND_BASE_URL` to a Laravel URL reachable **from that container**; `127.0.0.1` inside it points to the container itself. Likewise, deployed Laravel must use the deployed AI origin, without an `/api` suffix. Supply secrets in the hosting environment, enable the internal gate, and restrict access as appropriate. This service owns no persistent application database.

## Related Repositories

- [Backend — em_backend](https://github.com/Hsu-Hlaing-Htet/em_backend)
- [Frontend — em_frontend](https://github.com/Hsu-Hlaing-Htet/em_frontend)
- [AI — em_ai](https://github.com/Hsu-Hlaing-Htet/em_ai)

Developed by [Hsu-Hlaing-Htet](https://github.com/Hsu-Hlaing-Htet).
