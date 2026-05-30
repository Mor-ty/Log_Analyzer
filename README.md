<div align="center">

# K8s Log Analytics Platform

### AI-Powered Kubernetes Observability & Diagnostics

**Deliver faster incident response. Cut through log noise. Get root-cause analysis and actionable remediation in seconds.**

---

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018-61DAFB?style=flat-square&logo=react)](https://react.dev)
[![Docker](https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?style=flat-square&logo=docker)](https://www.docker.com)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2015-336791?style=flat-square&logo=postgresql)](https://www.postgresql.org)
[![Azure OpenAI](https://img.shields.io/badge/AI-Azure%20OpenAI-0078D4?style=flat-square&logo=microsoft-azure)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)

</div>

---

## Overview

K8s Log Analytics is a production-ready, containerised platform that transforms raw Kubernetes log data into structured, actionable intelligence. Engineers and SREs can either **upload log files** directly or **connect live to a Kubernetes cluster** and receive AI-driven diagnostics — including root-cause identification, anomaly detection, and ready-to-run `kubectl` remediation commands — all within a polished browser interface.

### What It Solves

| Pain Point | Platform Solution |
|---|---|
| Sifting through thousands of log lines manually | Smart log condensation removes noise before analysis — up to **90% token reduction** |
| Slow incident triage across multiple pods | Unified browser: browse namespaces → pods → containers → stream logs in one click |
| Opaque failure modes (OOMKilled, CrashLoopBackOff…) | AI identifies root cause and generates the exact `kubectl` command to fix it |
| Re-running expensive LLM calls for the same incident | Every analysis is persisted and restored instantly from session history |
| AI dependency risk | Rule-based fallback engine maintains diagnostics when the LLM is unavailable |

---

## Platform Capabilities

| Capability | Detail |
|---|---|
| **Log File Upload** | Drag-and-drop or browse to upload any `.log` file for immediate AI analysis |
| **Live Cluster Browser** | Connect to a running Kubernetes cluster — browse namespaces, pods, and containers and stream logs directly in the UI |
| **AI-Powered Analysis** | Azure OpenAI (GPT) identifies anomalies, classifies severity, surfaces root causes, and generates targeted `kubectl` fix commands |
| **Smart Log Condensation** | Regex-based normalisation deduplicates repetitive log patterns before LLM submission — reduces token usage by up to **90%** |
| **Non-Blocking Async Jobs** | Analysis is processed in a background thread pool; the UI polls job status without locking the browser tab |
| **Persistent Session History** | Every analysis result is saved to PostgreSQL and can be retrieved instantly — no re-running the LLM for repeat reviews |
| **Analytics Dashboard** | Visualise log-level distribution (pie chart), top offending resources (bar chart), and browse all sessions with severity badges |
| **Graceful Fallback Engine** | Rule-based diagnostics for common Kubernetes failure modes (`CrashLoopBackOff`, `OOMKilled`, `ImagePullBackOff`, etc.) activate automatically when the LLM is unreachable |

---

## Tech Stack

### Backend
| Component | Technology |
|---|---|
| Language & Runtime | Python 3.11 |
| Web Framework | FastAPI |
| ORM | SQLAlchemy 2 |
| Data Validation | Pydantic v2 |
| AI Integration | Azure OpenAI SDK (GPT) |
| Cluster Access | `kubectl` subprocess wrapper |
| Concurrency | `ThreadPoolExecutor` (4 workers) |

### Frontend
| Component | Technology |
|---|---|
| Framework | React 18 + TypeScript |
| Build Tool | Vite |
| Styling | Tailwind CSS |
| Charts | Recharts |
| Routing | React Router v6 |
| Icons | Lucide React |

### Infrastructure & Data
| Component | Technology |
|---|---|
| Containerisation | Docker + Docker Compose |
| Frontend Serving | Nginx (static + API reverse proxy) |
| Primary Database | PostgreSQL 15 |
| Cache / Queue | Redis 7 |

---

## Port Reference

| Service | Container Name | Host Port | Container Port | Purpose |
|---|---|---|---|---|
| Frontend | `k8s-log-analytics-frontend` | **8080** | 80 | React UI served by Nginx |
| Backend API | `k8s-log-analytics-backend` | **8000** | 8000 | FastAPI REST + Swagger docs |
| PostgreSQL | `k8s-log-analytics-db` | 5432 | 5432 | Persistent log & session storage |
| Redis | `k8s-log-analytics-redis` | *(internal)* | 6379 | Cache and job queue |

> Redis is not exposed to the host by default. Access it via `docker exec` if direct inspection is needed.

---

## Prerequisites

Before starting, ensure the following are available on the host machine:

| Requirement | Notes |
|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 4.x | Includes Docker Compose v2 |
| Azure OpenAI resource | **Optional** — the rule-based fallback analyser works without it |
| `kubectl` + valid `kubeconfig` | **Optional** — required only for live cluster browsing |

---

## Deployment: Docker Compose (Recommended)

This is the primary delivery method. All four services — frontend, backend, PostgreSQL, and Redis — start with a single command.

### Step 1 — Clone the repository

```bash
git clone <repo-url>
cd Log_Analyzer
```

### Step 2 — Configure environment variables

Copy the example and populate your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# ── Azure OpenAI ──────────────────────────────────────────────────
# Leave these blank to use the built-in rule-based fallback analyser
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT=gpt-5.4
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# ── Tuning (optional) ─────────────────────────────────────────────
AZURE_OPENAI_TEMPERATURE=0.1
AZURE_OPENAI_MAX_TOKENS=100000
```

### Step 3 — Build and start all containers

```bash
docker compose up -d --build
```

This will:
1. Build the Python backend image
2. Build the React frontend image (Vite production build + Nginx)
3. Pull PostgreSQL 15 and Redis 7 from Docker Hub
4. Start all four containers on the shared bridge network
5. Run database initialisation on first startup

> Build time is approximately 2–4 minutes on first run. Subsequent starts (without `--build`) take under 10 seconds.

### Step 4 — Verify all containers are healthy

```bash
docker compose ps
```

All four services should show `running` or `healthy`.

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

### Step 5 — Access the platform

| Service | URL |
|---|---|
| **Application UI** | http://localhost:8080 |
| **Backend REST API** | http://localhost:8000 |
| **Interactive API Docs (Swagger)** | http://localhost:8000/docs |
| **Health Check** | http://localhost:8000/health |

### Step 6 — Stop the platform

```bash
# Stop containers, preserve database volumes
docker compose down

# Stop containers AND wipe the database
docker compose down -v
```

---

## Containerisation Details

The platform is fully containerised using Docker Compose with a dedicated bridge network (`k8s-log-analytics-network`). All inter-service communication uses container DNS names (e.g. `postgres`, `redis`) — no hardcoded IPs.

### Backend container

- Base image: `python:3.11-slim`
- Installs all dependencies from `requirements.txt`
- Waits for PostgreSQL health check before starting (`depends_on: condition: service_healthy`)
- Mounts `~/.kube/config` read-only for Kubernetes cluster access
- Restarts automatically on failure (`restart: unless-stopped`)

### Frontend container

- Multi-stage build: Node 18 (Vite build) → Nginx Alpine (serve)
- Nginx configured as a reverse proxy: `/api/*` → backend:8000, all other routes → React SPA
- Restarts automatically on failure

### Database persistence

PostgreSQL data is stored in a named Docker volume (`postgres_data`) and survives container restarts. Run `docker compose down -v` only when you intentionally want to reset all data.

---

## Local Development Setup

Use this for active development with hot reload. Requires Python 3.11+ and Node 18+.

### Backend (hot reload)

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# Set environment (use SQLite to avoid needing a local Postgres)
set DATABASE_URL=sqlite:///./logs.db          # Windows
export DATABASE_URL=sqlite:///./logs.db       # macOS / Linux

uvicorn app.main:app --reload --port 8000
```

### Frontend (hot reload)

```bash
cd frontend
npm install
npm run dev
# Starts on http://localhost:5173
```

The Vite dev server automatically proxies `/api/*` requests to `http://localhost:8000`.

---

## Kubernetes Cluster Access

The backend mounts the host kubeconfig into the container read-only:

```yaml
volumes:
  - ~/.kube/config:/kubeconfig/config:ro
```

**Docker Desktop** — enable the built-in Kubernetes cluster under *Settings → Kubernetes → Enable Kubernetes*. It works immediately with no additional configuration.

**Remote cluster** — ensure `kubectl get nodes` succeeds on the host before starting the containers. The mounted kubeconfig is used inside the container automatically.

**Disable cluster features** — remove or comment out the `KUBECONFIG` environment variable in `docker-compose.yml` if cluster access is not required.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | No | — | Azure OpenAI resource endpoint URL |
| `AZURE_OPENAI_API_KEY` | No | — | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | No | `gpt-5.4` | Name of the deployed model |
| `AZURE_OPENAI_API_VERSION` | No | `2024-12-01-preview` | Azure OpenAI API version |
| `AZURE_OPENAI_TEMPERATURE` | No | `0.1` | LLM sampling temperature (0–1) |
| `AZURE_OPENAI_MAX_TOKENS` | No | `100000` | Maximum tokens per LLM response |
| `DATABASE_URL` | Yes | `sqlite:///./logs.db` | SQLAlchemy connection string |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL |
| `KUBECONFIG` | No | — | Path to kubeconfig inside the container |
| `LOG_RETENTION_DAYS` | No | `30` | Days before automatic log cleanup |

---

## API Reference

Full interactive documentation is available at **http://localhost:8000/docs** (Swagger UI) when the platform is running.

```
── System ──────────────────────────────────────────────────────────
GET  /health                              Liveness check
GET  /docs                                Swagger UI

── Log Analysis ────────────────────────────────────────────────────
POST /api/logs/upload                     Upload a .log file (multipart/form-data)
POST /api/logs/analyze                    Start async AI analysis → returns { job_id }
GET  /api/logs/jobs/{job_id}              Poll job status and retrieve result
GET  /api/logs/sessions                   List all saved analysis sessions
GET  /api/logs/entries/{resource_id}      Paginated log entry listing

── Kubernetes ──────────────────────────────────────────────────────
GET  /api/k8s/health                      Cluster connectivity and health summary
GET  /api/k8s/namespaces                  List all namespaces
GET  /api/k8s/pods/{namespace}            List pods within a namespace
GET  /api/k8s/logs/{namespace}/{pod}      Fetch and optionally persist pod logs
```

---

## Project Structure

```
Log_Analyzer/
├── docker-compose.yml          # Full-stack container orchestration
├── .env                        # Runtime secrets (not committed to source control)
├── .env.example                # Template for required environment variables
├── README.md
├── start.sh / start.bat        # Convenience startup scripts
├── docs/                       # Implementation notes, fix logs, migration guides
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI entry point, CORS, router registration
│       ├── api/
│       │   ├── logs.py         # Upload, analyse, job polling, session endpoints
│       │   └── kubernetes.py   # Namespace, pod, and log streaming endpoints
│       ├── core/
│       │   ├── config.py       # Pydantic settings (reads from .env)
│       │   └── database.py     # SQLAlchemy engine and session factory
│       ├── models/
│       │   ├── log.py          # ORM models: LogEntry, K8sResource, LogAnalysis, LogSession
│       │   └── schemas.py      # Pydantic request / response schemas
│       └── services/
│           ├── log_parser.py   # Regex-based multi-format log parser
│           ├── k8s_collector.py# kubectl subprocess wrapper
│           └── llm_analyzer.py # LLM orchestration, log condensation, fallback engine
│
└── frontend/
    ├── Dockerfile              # Multi-stage: Node build → Nginx serve
    ├── nginx.conf              # SPA routing + /api reverse proxy config
    ├── index.html
    └── src/
        ├── App.tsx             # Application shell, navigation, live status bar
        ├── context/
        │   └── AnalysisContext.tsx   # Global async job state management
        ├── pages/
        │   ├── UploadPage.tsx        # File upload and analysis trigger
        │   ├── ClusterBrowserPage.tsx# Live K8s namespace / pod browser
        │   └── DashboardPage.tsx     # Charts, severity summary, session history
        ├── services/
        │   └── api.ts                # Fully-typed REST API client
        └── types/
            └── index.ts              # Shared TypeScript type definitions
```

---

## Supplementary Documentation

Extended implementation notes, migration guides, and fix logs are available in the [`docs/`](docs/) directory.
