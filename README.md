# OCR Adjudicator — Backend

Lightweight FastAPI backend for the OCR Adjudicator project. This README covers local development, Docker, docker-compose, and Render deployment notes.

## Contents
- Overview
- Requirements
- Environment variables
- Local setup & run
- Docker (local) & docker-compose
- Deploy on Render (Docker)
- Database & migrations
- Security notes
- Troubleshooting

## Overview
This service exposes FastAPI endpoints for claim submission, adjudication, and persistence using PostgreSQL.

## Requirements
- macOS / Linux
- Python 3.10+
- Docker & docker-compose (for containerized workflows)
- (Optional) Homebrew for installing utilities

## Environment variables
Do NOT commit secrets to git. Replace values in the examples below.

Required:
- DATABASE_URL — PostgreSQL connection string (e.g. postgresql://user:pass@host:5432/dbname)
- GEMINI_API_KEY — API key for external AI service
Optional:
- PORT — default service port (if using Docker or override)

Example `.env` (do NOT commit):
```
DATABASE_URL=postgresql://<user>:<pass>@<host>:5432/<db>
GEMINI_API_KEY=your_api_key_here
PORT=10000
```

## Local setup & run (venv)
macOS / Linux:
```bash
cd /Users/vyomrohila/Documents/coding/OCR_Adjudicator/Backend

# Create and activate virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (ensure requirements.txt exists)
pip install -r requirements.txt

# Export env vars (or create .env and load)
export DATABASE_URL="postgresql://user:pass@localhost:5432/plum_claims"
export GEMINI_API_KEY="REPLACE_ME"

# Run dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

If your project uses different dependency tooling (poetry/pyproject), adapt accordingly.

## Docker (local) & docker-compose
A Dockerfile is included (or add one). Use the project's root docker-compose.yml to run DB + backend + frontend.

From repo root:
```bash
# Build and start services
docker-compose up --build

# Stop & remove containers
docker-compose down
```

The compose file starts a Postgres service `db` and the backend uses `DATABASE_URL` pointed to `db`. Adjust compose/service env if needed.

## Deploy on Render (Docker)
Recommended: use a Dockerfile for the backend and set environment variables in Render (do not push .env).

Steps:
1. Add Backend/Dockerfile (exposes PORT; runs uvicorn).
2. Push repository to GitHub.
3. On Render: New → Web Service → Connect repo → select Docker environment and Backend/Dockerfile.
4. In Render service settings add environment variables (DATABASE_URL, GEMINI_API_KEY).
5. Create a managed Postgres on Render or use external DB and set its connection string in DATABASE_URL.
6. Add post-deploy or build commands to run DB migrations if you use alembic.

## Database & migrations
- If using Alembic: run `alembic upgrade head` after DB is ready.
- If using SQLAlchemy without migrations: the app may auto-create tables — ensure this is acceptable for production.
- For local testing, run a local Postgres instance or use docker-compose included.

## Security notes
- Remove secrets from repo (.env) and add `.env` to `.gitignore`.
- Use secrets manager or Render environment variables for production secrets.
- Use network policies / secure DB credentials for production DB.

## Troubleshooting
- "psycopg2 / asyncpg errors": confirm DATABASE_URL is correct and DB accepts connections.
- "uvicorn permission/port errors": change PORT env or run with higher privileges.
- "Missing dependency": ensure `requirements.txt` lists all libs (fastapi, uvicorn, sqlalchemy/asyncpg, python-multipart if file upload).

If you want, I can:
- generate a sample Backend/Dockerfile,
- produce a minimal requirements.txt from your environment files,
- or add a small `render.yaml` for Render deployment.
