---
title: Gotham Telekinesis API
emoji: 🦇
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

<p align="center">
  <strong>🦇 Gotham Telekinesis API</strong>
</p>

<p align="center">
  FastAPI backend for authentication, health monitoring, and optional server-side hand tracking.
</p>

<p align="center">
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" /></a>
  <a href="https://www.postgresql.org"><img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" /></a>
  <a href="https://huggingface.co/spaces"><img src="https://img.shields.io/badge/Deploy-HuggingFace-FFD21E?style=flat-square&logo=huggingface&logoColor=black" alt="Hugging Face" /></a>
  <a href="https://www.docker.com"><img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker" /></a>
</p>

<p align="center">
  <a href="https://github.com/aliashrafabbasi/AI-Telekinesis-Simulator-frontend"><strong>Frontend App</strong></a>
  &nbsp;·&nbsp;
  <a href="https://aliashrafabbasi-gotham-telekinesis-api.hf.space/health/live"><strong>Live API</strong></a>
</p>

---

## Overview

This repository powers the **Gotham Telekinesis** backend — a FastAPI service that provides JWT-based user authentication and, in local environments, server-side hand tracking over WebSocket.

| Capability | Production (HF Space) | Local (Docker) |
|------------|:---------------------:|:--------------:|
| User authentication | ✓ | ✓ |
| PostgreSQL storage | ✓ (Neon) | ✓ (Docker) |
| Server-side webcam tracking | — | ✓ |
| Health endpoints | ✓ | ✓ |

> In production, the React frontend performs hand tracking in the browser. This API serves `/auth/*` endpoints only on Hugging Face.

---

## Table of Contents

- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Tech Stack](#tech-stack)

---

## Architecture

```mermaid
flowchart TB
    subgraph Prod["Production"]
        FE["React Frontend · Netlify"]
        API["FastAPI · Hugging Face"]
        DB[("Neon PostgreSQL")]
        FE -->|"HTTPS /auth/*"| API
        API --> DB
    end

    subgraph Local["Local Development"]
        FE2["React · localhost:5173"]
        API2["FastAPI · Docker"]
        DB2[("Postgres · Docker")]
        CAM["Webcam + MediaPipe"]
        FE2 -->|"WebSocket"| API2
        FE2 -->|"HTTPS /auth/*"| API2
        API2 --> DB2
        CAM --> API2
    end
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|:------:|----------|-------------|
| `POST` | `/auth/register` | Create account — `{ email, username, password }` |
| `POST` | `/auth/login` | Obtain JWT — `{ email, password }` |
| `GET` | `/auth/me` | Current user — `Authorization: Bearer <token>` |
| `POST` | `/auth/logout` | Invalidate session (client clears token) |

Username must match `^[a-zA-Z0-9_]+$`.

### WebSockets *(local server mode only)*

| Endpoint | Purpose |
|----------|---------|
| `/ws?token=<jwt>` | Hand position and gesture frames |
| `/ws/preview?token=<jwt>` | JPEG camera preview stream |

The camera activates when an authenticated client connects.

### Health

| Endpoint | Description |
|----------|-------------|
| `GET /health/live` | Process liveness check |
| `GET /health/ready` | Database and camera readiness |
| `GET /health` | Legacy health summary |

---

## Quick Start

### Docker Compose *(recommended)*

```bash
git clone https://github.com/aliashrafabbasi/AI-Telekinesis-Simulator.git
cd AI-Telekinesis-Simulator
docker compose up --build
```

API available at `http://localhost:7860`

### Manual Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # configure JWT_SECRET and DATABASE_URL
alembic upgrade head
uvicorn app.main:app --reload --port 7860
```

### Verify

```bash
# Health check
curl http://127.0.0.1:7860/health/live

# Register
curl -X POST http://127.0.0.1:7860/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@gotham.com","username":"demo","password":"secret123"}'

# Login
curl -X POST http://127.0.0.1:7860/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@gotham.com","password":"secret123"}'
```

---

## Configuration

| Variable | Description |
|----------|-------------|
| `ENVIRONMENT` | `development` or `production` |
| `DATABASE_URL` | Async PostgreSQL URL — `postgresql+asyncpg://...` |
| `JWT_SECRET` | HS256 signing key (32+ characters in production) |
| `JWT_EXPIRE_MINUTES` | Token lifetime (default: `60`) |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `LOG_LEVEL` | Logging verbosity — `DEBUG`, `INFO`, `WARNING` |

<details>
<summary><strong>Example — production secrets (Hugging Face)</strong></summary>

| Secret | Value |
|--------|-------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://...@neon.tech/neondb?ssl=require` |
| `JWT_SECRET` | `<random-32-char-string>` |
| `JWT_EXPIRE_MINUTES` | `60` |
| `CORS_ORIGINS` | `https://your-site.netlify.app,http://localhost:5173` |
| `LOG_LEVEL` | `INFO` |

</details>

---

## Deployment

### Hugging Face Spaces

1. Create a Space with **SDK: Docker**
2. Push this repository to the Space remote
3. Configure secrets (see table above)
4. Run database migrations once from your local machine:

   ```bash
   export DATABASE_URL="postgresql+asyncpg://..."
   alembic upgrade head
   ```

5. Confirm deployment: `curl https://YOUR-SPACE.hf.space/health/live`

> After deploying the frontend, update `CORS_ORIGINS` with your Netlify URL or auth requests will be blocked.

### Docker (standalone)

```bash
docker build -t gotham-telekinesis .

docker run --rm -p 7860:7860 \
  --device /dev/video0 \
  -e ENVIRONMENT=development \
  -e DATABASE_URL=postgresql+asyncpg://telekinesis:password@host.docker.internal:5432/telekinesis \
  -e JWT_SECRET=your-local-secret-min-32-chars \
  -e CORS_ORIGINS=http://localhost:5173 \
  gotham-telekinesis
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | FastAPI |
| Database | PostgreSQL · SQLAlchemy async · asyncpg |
| Migrations | Alembic |
| Auth | JWT (HS256) |
| Hand tracking | MediaPipe Hands · OpenCV *(local only)* |
| Container | Docker · docker-compose |

---

<p align="center">
  Built by <a href="https://github.com/aliashrafabbasi">aliashrafabbasi</a>
</p>
