# CoachAI (Multimodal Learning Coach)

CoachAI is a **Streamlit-based multimodal learning coach**. It helps learners:

- Ask questions (text-only or with an uploaded image)
- Retrieve relevant lesson material from a knowledge base (RAG)
- Generate grounded explanations (citing retrieved document IDs when relevant)
- Generate practice questions and evaluate answers

The project follows a **layered architecture** and is implemented primarily under `coachai/` (core layers) and `ui/` (Streamlit UI layer). It integrates with:

- **Mistral API** for remote LLM + OCR / vision understanding (default)
- **Supabase** for authentication, lesson storage, and file attachments
- **Postgres + pgvector** for vector search
- **Cohere embeddings** for embeddings

## What’s in this repo

- `app.py`
  - Streamlit entrypoint.
  - Handles sign-in/sign-up via Supabase.
  - Lets you manage lessons (create/delete, visibility).
  - Runs the RAG + generation flow via the `coachai/` + `ui/` modules.

- `ui/`
  - Streamlit/UI-layer code.
  - `learning_coach_agent.py`: UI-facing orchestration used by `app.py`.
  - `image_processor.py`: Streamlit-friendly image validation/resizing.

- `coachai/`
  - Core layered architecture implementation.
  - `clients/`: outbound integrations (Supabase, Postgres/pgvector, Cohere, Mistral).
  - `repositories/`: data access (e.g. `KnowledgeRepository`).
  - `services/`: business logic (e.g. `CoachService`, model handling).
  - `controllers/`: transport adapters for services.
  - `core/`: configuration and shared utilities.

- `src/`
  - Legacy code kept temporarily for reference during the refactor.

- `api/`
  - Optional FastAPI app (`api/main.py`) exposing knowledge-base endpoints.
  - Includes “protected” endpoints (`api/protected_routes.py`) meant for trusted backends.

## Architecture (high level)

Dependency direction:

`api/ui` -> `controllers` -> `services` -> `repositories` -> `clients`

- **UI (Streamlit)**: `app.py`
- **UI agent/orchestration**: `ui/learning_coach_agent.py` (`LearningCoachAgent`)
- **Service layer**: `coachai/services/coach_service.py` (`CoachService`)
- **Repository layer**: `coachai/repositories/knowledge_repository.py` (`KnowledgeRepository`)
  - Loads lessons from Supabase (if configured)
  - Searches via pgvector if Postgres is available; otherwise does client-side cosine similarity
- **Model backend**: `coachai/services/model_handler.py`
  - Default: remote Mistral API (requires `MISTRAL_API_KEY`)

## Requirements

Python dependencies are listed in `requriments.txt` (note the filename).

Key packages used by the app:

- `streamlit`
- `supabase`
- `python-dotenv` (imported as `dotenv`)
- `psycopg2` / `psycopg2-binary` (optional, for Postgres)
- `sentence_transformers` (embeddings fallback)

If you want to use Cohere embeddings, you also need the `cohere` Python package installed.

## Configuration

The code loads environment variables from a `.env` file located at the repository root (see `coachai/core/config.py` and `coachai/__init__.py`).

### Required (for default remote-model mode)

- `MISTRAL_API_KEY`

### Optional (enable Supabase persistence + auth)

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` (used by browser clients)
- `SUPABASE_SERVICE_ROLE_KEY` (privileged operations; do not expose publicly)
- `SUPABASE_STORAGE_BUCKET` (defaults to `attachments`)

### Optional (enable pgvector search)

- `SUPABASE_DB_URL` (Postgres DSN used by `psycopg2`)
- `PGVECTOR_DIMENSION` (defaults to `384`)

### Optional (prefer Cohere for embeddings)

- `COHERE_API_KEY`
- `COHERE_MODEL` (defaults to `small` in this repo)

### Optional (server-side RAG endpoints)

- `USE_SERVER_SIDE_RAG` (`true` / `false`)

## Running the Streamlit app

1. Create and activate a virtual environment.
2. Install dependencies.
3. Set required environment variables (at least `MISTRAL_API_KEY`).
4. Run:

```bash
streamlit run app.py
```

The UI provides:

- **Ask**: question + optional image upload.
- **Practice**: generate a question for one of your saved topics and submit an answer.
- **Manage**: create, list, and delete lessons (topics).

## Running the optional API

The FastAPI app lives in `api/main.py` and runs on port `8080`:

```bash
python api/main.py
```

Endpoints:

- `GET /health`
- `GET /api/v1/entries/` (CRUD for `knowledge_entries` in the API’s SQLite DB)
- `POST /api/v1/search/` (semantic search over API entries)
- `POST /api/v1/protected/*` (requires `x-service-key` header matching `SUPABASE_SERVICE_ROLE_KEY`)

Note: the Streamlit app’s primary knowledge base integration is via Supabase (`coachai/repositories/knowledge_repository.py`). The API module is an additional component.

## Notes / gotchas

- The repo includes a `.env` file locally, but it is gitignored.
- `requriments.txt` is intentionally referenced by that name in this repo (typo in filename).
- Supabase service role key should **never** be used in a public client.

