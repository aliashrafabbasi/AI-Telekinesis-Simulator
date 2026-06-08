# Gotham Telekinesis — Backend

FastAPI hand-tracking server with PostgreSQL authentication.

## Prerequisites

- Python 3.12+
- PostgreSQL (local or Docker)
- Webcam (for hand tracking)

## PostgreSQL (Docker)

```bash
docker run --name telekinesis-postgres \
  -e POSTGRES_USER=telekinesis \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=telekinesis \
  -p 5432:5432 \
  -d postgres:16
```

## Setup

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

- `ws://127.0.0.1:8000/ws?token=...`
- `ws://127.0.0.1:8000/ws/preview?token=...`

## Health

| Path | Purpose |
|------|---------|
| `GET /health/live` | Process alive |
| `GET /health/ready` | DB + camera readiness (503 if not ready) |
| `GET /health` | Legacy summary |

## Quick test (curl)

```bash
# Register
curl -s -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"batman@gotham.com","username":"batman","password":"secret123"}'

# Login
curl -s -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"batman@gotham.com","password":"secret123"}'

# Me (replace TOKEN)
curl -s http://127.0.0.1:8000/auth/me -H "Authorization: Bearer TOKEN"
```

## Production notes

- Set `ENVIRONMENT=production` and a strong `JWT_SECRET`
- Set `CORS_ORIGINS` to your real frontend URL(s)
- Run behind HTTPS; never expose JWT over plain HTTP in production
