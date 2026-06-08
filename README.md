---
title: Gotham Telekinesis API
emoji: 🦇
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Gotham Telekinesis — Backend

FastAPI hand-tracking server with PostgreSQL authentication.

## Prerequisites

- Python 3.12+ (local dev)
- PostgreSQL (local, Docker, or Neon/Supabase for production)
- Webcam (local dev only — cloud deploy has no server-side camera)

## Docker (local or Hugging Face)

### Quick start with Docker Compose

```bash
docker compose up --build
```

API: `http://localhost:7860`

### Build and run manually

```bash
docker build -t gotham-telekinesis .

docker run --rm -p 7860:7860 \
  -e ENVIRONMENT=development \
  -e DATABASE_URL=postgresql+asyncpg://telekinesis:password@host.docker.internal:5432/telekinesis \
  -e JWT_SECRET=your-local-test-secret-min-32-chars \
  -e JWT_EXPIRE_MINUTES=60 \
  -e CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173 \
  -e LOG_LEVEL=INFO \
  --add-host=host.docker.internal:host-gateway \
  gotham-telekinesis
```

On Linux, `--add-host=host.docker.internal:host-gateway` lets the container reach Postgres on your host.

## Hugging Face Spaces deployment

1. Create a new Space with **SDK: Docker**
2. Push this repo to the Space git remote
3. Set **Secrets** in Space settings:

| Secret | Description |
|--------|-------------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://...` (Neon/Supabase) |
| `JWT_SECRET` | Strong random string (32+ chars) |
| `JWT_EXPIRE_MINUTES` | `60` |
| `CORS_ORIGINS` | Your Netlify URL, e.g. `https://your-app.netlify.app` |
| `LOG_LEVEL` | `INFO` |

4. Run migrations once against your cloud DB (locally):

```bash
export DATABASE_URL="postgresql+asyncpg://..."
alembic upgrade head
```

5. Test: `curl https://YOUR-SPACE.hf.space/health/live`

**Note:** Hand tracking uses a server-side webcam and will not work on Hugging Face cloud. Auth API deploys fine; move camera to the browser for full cloud gameplay.

## Local development (without Docker)

### PostgreSQL (Docker)

```bash
docker run --name telekinesis-postgres \
  -e POSTGRES_USER=telekinesis \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=telekinesis \
  -p 5432:5432 \
  -d postgres:16
```

### Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set JWT_SECRET to a long random string
alembic upgrade head
uvicorn app.main:app --reload
```

## Environment

| Variable | Description |
|----------|-------------|
| `ENVIRONMENT` | `development` or `production` |
| `DATABASE_URL` | PostgreSQL async URL |
| `JWT_SECRET` | HS256 signing secret (required in production) |
| `JWT_EXPIRE_MINUTES` | Token lifetime |
| `CORS_ORIGINS` | Comma-separated frontend origins |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, … |

## Auth API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | `{ email, username, password }` |
| POST | `/auth/login` | `{ email, password }` |
| GET | `/auth/me` | Bearer token required |
| POST | `/auth/logout` | Bearer token (client clears token) |

WebSockets require `?token=<jwt>` (camera starts only when an authenticated client connects):

- `ws://127.0.0.1:8000/ws?token=...` (local uvicorn)
- `wss://YOUR-SPACE.hf.space/ws?token=...` (production)

## Health

| Path | Purpose |
|------|---------|
| `GET /health/live` | Process alive |
| `GET /health/ready` | DB + camera readiness (503 if not ready) |
| `GET /health` | Legacy summary |

## Quick test (curl)

```bash
# Register
curl -s -X POST http://127.0.0.1:7860/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"batman@gotham.com","username":"batman","password":"secret123"}'

# Login
curl -s -X POST http://127.0.0.1:7860/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"batman@gotham.com","password":"secret123"}'

# Me (replace TOKEN)
curl -s http://127.0.0.1:7860/auth/me -H "Authorization: Bearer TOKEN"
```

## Production notes

- Set `ENVIRONMENT=production` and a strong `JWT_SECRET`
- Set `CORS_ORIGINS` to your real frontend URL(s)
- Run behind HTTPS; never expose JWT over plain HTTP in production
