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

FastAPI server with JWT authentication and optional server-side hand tracking (MediaPipe + webcam).

**Frontend repo:** [AI-Telekinesis-Simulator-frontend](https://github.com/aliashrafabbasi/AI-Telekinesis-Simulator-frontend)

**Live API:** `https://aliashrafabbasi-gotham-telekinesis-api.hf.space`

---

## What this project does

| Feature | Production (HF) | Local Docker |
|---------|-----------------|--------------|
| **Auth API** | ✅ Register, login, JWT | ✅ Same |
| **PostgreSQL** | ✅ Neon cloud DB | ✅ Docker Postgres |
| **Server webcam tracking** | ❌ No camera on cloud | ✅ WebSocket hand tracking |

In **production**, the React frontend runs hand tracking in the browser. This backend only serves **authentication** and health checks on Hugging Face.

For **local development**, Docker can also run server-side camera tracking over WebSocket when the frontend uses `VITE_TRACKING_MODE=server`.

---

## Architecture

```
Production (deployed)
─────────────────────
Browser (Netlify)  ──HTTPS──►  HF Space (this API)  ──►  Neon PostgreSQL
     │                              │
     └── hand tracking              └── /auth/* only
         (MediaPipe in browser)

Local dev (server mode)
───────────────────────
Browser (localhost:5173)  ──WS──►  Docker API (this repo)  ──►  Postgres
                                        │
                                        └── webcam + MediaPipe
```

---

## Auth API

| Method | Path | Body / headers |
|--------|------|----------------|
| POST | `/auth/register` | `{ email, username, password }` |
| POST | `/auth/login` | `{ email, password }` |
| GET | `/auth/me` | `Authorization: Bearer <token>` |
| POST | `/auth/logout` | Bearer token (client clears token) |

Username must match `^[a-zA-Z0-9_]+$` (no spaces).

---

## WebSockets (local server mode only)

Requires `?token=<jwt>` — camera starts when an authenticated client connects:

| Path | Purpose |
|------|---------|
| `/ws` | Hand control frames (position, gesture) |
| `/ws/preview` | JPEG camera preview |

Example: `ws://127.0.0.1:7860/ws?token=...`

Not used in production browser-mode deploy.

---

## Health

| Path | Purpose |
|------|---------|
| `GET /health/live` | Process alive |
| `GET /health/ready` | DB + camera readiness |
| `GET /health` | Legacy summary |

---

## Docker (local)

### Quick start

```bash
docker compose up --build
```

API: `http://localhost:7860`

### Manual run

```bash
docker build -t gotham-telekinesis .

docker run --rm -p 7860:7860 \
  -e ENVIRONMENT=development \
  -e DATABASE_URL=postgresql+asyncpg://telekinesis:password@host.docker.internal:5432/telekinesis \
  -e JWT_SECRET=your-local-test-secret-min-32-chars \
  -e JWT_EXPIRE_MINUTES=60 \
  -e CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173 \
  -e LOG_LEVEL=INFO \
  --device /dev/video0 \
  gotham-telekinesis
```

On Linux, map the webcam with `--device /dev/video0` (or use `docker-compose.yml` which handles this).

---

## Hugging Face Spaces deployment

1. Create a Space with **SDK: Docker**
2. Push this repo to the Space git remote
3. Set **Secrets** in Space settings:

| Secret | Example |
|--------|---------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://...@...neon.tech/neondb?ssl=require` |
| `JWT_SECRET` | Strong random string (32+ chars) |
| `JWT_EXPIRE_MINUTES` | `60` |
| `CORS_ORIGINS` | `https://gotham-telekinesis.netlify.app,http://localhost:5173` |
| `LOG_LEVEL` | `INFO` |

4. Run migrations against your cloud DB (once, from your machine):

```bash
export DATABASE_URL="postgresql+asyncpg://..."
alembic upgrade head
```

5. Verify: `curl https://YOUR-SPACE.hf.space/health/live`

> **Important:** Set `CORS_ORIGINS` to your Netlify URL after frontend deploy, or login will fail with CORS errors.

---

## Local development (without Docker)

### PostgreSQL

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
uvicorn app.main:app --reload --port 7860
```

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `ENVIRONMENT` | `development` or `production` |
| `DATABASE_URL` | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `JWT_SECRET` | HS256 signing secret (required in production) |
| `JWT_EXPIRE_MINUTES` | Token lifetime (default `60`) |
| `CORS_ORIGINS` | Comma-separated frontend origins |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, … |

---

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

---

## Tech stack

- **FastAPI** — REST + WebSocket
- **SQLAlchemy async** + **asyncpg** — PostgreSQL
- **Alembic** — migrations
- **MediaPipe Hands** — server-side tracking (local Docker only)
- **OpenCV** — webcam capture (local Docker only)
- **JWT (HS256)** — authentication

---

## Production notes

- Set `ENVIRONMENT=production` and a strong `JWT_SECRET`
- Set `CORS_ORIGINS` to your real Netlify URL(s)
- Use HTTPS everywhere; never send JWT over plain HTTP in production
- Hand tracking in production runs in the **browser frontend**, not on this server
