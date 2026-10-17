# CHEMI — Chemistry tutor

CHEMI is a Vietnamese high-school chemistry assistant. It explains compounds, shows chemical structures, reads English names, and creates practice quizzes. Chemical names use English nomenclature.

The application runs as a Cloudflare Python Worker with FastAPI and LangGraph. The Worker also serves the chat interface at https://chemi.quangiz.me.

## Request flow

```text
Browser → Worker/ASGI → FastAPI dependencies → query service
                                            ├─ D1 conversation checkpoints
                                            ├─ D1 FTS5 + Vectorize retrieval
                                            └─ LangGraph → OpenRouter → tools
Response ← validated text, citations, quiz, image, and audio artifacts
```

| Location | Responsibility |
|---|---|
| `backend/src/worker.py` | Adapt Cloudflare requests to ASGI |
| `backend/src/app/main.py` | Register routes, middleware, and error handlers |
| `api/` | HTTP contracts, authentication, rate limits, and error responses |
| `schemas/` | Validate requests, responses, and quiz data |
| `services/` | Query workflow, model adapter, memory, retrieval, and artifact processing |
| `tools/factory.py` | Model-callable image search, speech, and quiz generation |
| `backend/knowledge/` | Small source corpus for retrieval |
| `backend/tests/` | Offline tests using fake bindings and HTTP providers |

## Local setup

Requirements: Python 3.13, Node.js 22 or newer, and uv 0.13.1. The lockfiles pin dependency versions.

```bash
cd backend
npm ci
uv sync --frozen
cp .dev.vars.example .dev.vars
```

Edit `.dev.vars`. Set `OPENROUTER_API_KEY`. Set `API_KEYS` to a random application access key. Keep `APP_ENV=local` and `RAG_ENABLED=false` for a basic local run.

```bash
npx wrangler d1 execute chemi --local --file schema.sql
uv run pywrangler dev
```

Open http://localhost:8787. Use **Mã truy cập** to enter the application access key. The browser keeps this key in tab session storage. It never receives the provider key.

| Setting | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | Required provider credential |
| `API_KEYS` | Comma-separated application access keys. Required in production |
| `APP_ENV` | `local`, `test`, or `production` |
| `LLM_MODEL` | Agent model, default `openai/gpt-6-luna` |
| `QUIZ_MODEL` | Quiz model, default `openai/gpt-oss-120b` |
| `TTS_MODEL`, `TTS_VOICE` | Speech model and voice |
| `SERPAPI_KEY` | Optional general image search. Without it, PubChem supplies compound structure diagrams |
| `RAG_ENABLED` | Ground explanations with the knowledge corpus |
| `CORS_ORIGINS` | Optional comma-separated browser origin allowlist |
| `RETRIEVAL_MIN_SCORE` | Minimum semantic similarity, default `0.65` |

Worker settings come from request bindings. They do not use `os.environ`. Local `.dev.vars` and production Worker secrets have separate lifecycles.

## Verification

From the repository root:

```bash
make check
```

This runs lint, formatting checks, offline tests, and a small lexical retrieval evaluation. Tests need no provider credentials. The eight-case evaluation is a smoke set, not a production accuracy estimate.

The HTTP model adapter preserves image inputs, tool calls, tool results, and token usage. It avoids the OpenAI SDK and tiktoken in the Worker bundle. It supports asynchronous calls. Streaming is not implemented.

## Retrieval and memory

The ingestion script splits Markdown into overlapping chunks with stable IDs. It stores text in D1 FTS5 and creates 768-dimensional Workers AI embeddings in Vectorize. Query retrieval combines keyword and semantic ranks with reciprocal rank fusion.

Explanations cite retrieved chunk IDs. The server removes unknown IDs and abstains without evidence or a valid citation. Citation filtering does not prove factual entailment. Exercises and image recognition use separate flows. Quiz schema validation does not prove answer correctness.

D1Saver stores LangGraph checkpoints and pending writes. The client reuses a `thread_id`. The internal key includes the access-key identity. Callers sharing an access key also share its identity; this is not individual user authentication. Historical public threads from the earlier unscoped prototype are not imported into authenticated identities.

## Deployment

See [backend/DEPLOYMENT.md](backend/DEPLOYMENT.md). The deployment config includes D1, Vectorize, Workers AI, a rate limiter, observability, and the `chemi.quangiz.me` custom domain. R2 must be activated and its binding enabled before live audio storage works.

The GitHub workflow runs `lint` and `test` for pull requests. On `main`, it then applies the additive schema, uploads knowledge, deploys, and runs health/readiness smoke checks. The deploy job requires `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` repository secrets.

The local learning material remains under the ignored `learn/` directory. Its four short lessons cover backend foundations, agents/RAG, production behavior, and deployment.
