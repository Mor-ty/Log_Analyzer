# K8s Log Analytics

> AI-powered Kubernetes log analysis platform — upload log files or connect live to your cluster, get structured diagnostics, root-cause analysis, and actionable kubectl remediation commands in seconds.

---

## Features

| Capability | Detail |
|---|---|
| **File Upload** | Upload `.log` files through the GUI for immediate AI analysis |
| **Live K8s Cluster** | Browse namespaces, pods, and containers; stream logs via `kubectl` |
| **AI Analysis** | Azure OpenAI (GPT) detects anomalies, root causes, and generates `kubectl` fixes |
| **Smart Condensation** | Normalises and deduplicates log patterns before sending to LLM — up to 90% token reduction |
| **Async Jobs** | Analysis runs in a background thread pool; frontend polls non-blocking job status |
| **Session History** | Every analysis auto-saved; restore any previous result without re-running LLM |
| **Dashboard** | Log-level pie chart, top-resource bar chart, and session browser with severity badges |
| **Graceful Fallback** | Rule-based analyser (CrashLoopBackOff, OOMKilled, ImagePullBackOff…) when LLM is unavailable |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Browser  (localhost:8080)                     │
│                                                                  │
│  ┌──────────────┐  ┌────────────────────┐  ┌────────────────┐  │
│  │  Upload Page  │  │  Cluster Browser   │  │   Dashboard    │  │
│  │  (file drop)  │  │  (namespace/pod)   │  │  (charts +     │  │
│  └──────┬───────┘  └────────┬───────────┘  │   sessions)    │  │
│         │                   │              └───────┬────────┘  │
│         └───────────────────┴──────────────────────┘           │
│                   React + TypeScript + Tailwind                  │
│                   Vite · Recharts · React Router                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP  (port 8000)
┌──────────────────────────▼──────────────────────────────────────┐
│                 FastAPI Backend  (localhost:8000)                 │
│                                                                  │
│  POST /api/logs/upload          ← file upload + parse           │
│  POST /api/logs/analyze         ← trigger async LLM job         │
│  GET  /api/logs/jobs/{id}       ← poll job status               │
│  GET  /api/logs/sessions        ← session history               │
│  GET  /api/k8s/namespaces       ← list namespaces via kubectl   │
│  GET  /api/k8s/pods/{ns}        ← list pods                     │
│  GET  /api/k8s/logs/{ns}/{pod}  ← stream pod logs               │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  LogParser  │  │ K8sCollector │  │    LLMLogAnalyzer      │ │
│  │  (regex)    │  │  (kubectl    │  │  ┌──────────────────┐  │ │
│  └─────────────┘  │  subprocess) │  │  │ condense context │  │ │
│                   └──────────────┘  │  │ → Azure OpenAI   │  │ │
│                                     │  │ → fallback rules │  │ │
│  ThreadPoolExecutor (4 workers)     │  └──────────────────┘  │ │
│  _jobs dict  (in-memory job store)  └────────────────────────┘ │
└──────────────┬──────────────────────────────────────────────────┘
               │
   ┌───────────┴───────────┐
   │                       │
┌──▼──────────────┐  ┌─────▼──────────┐
│   PostgreSQL    │  │     Redis      │
│  (logs, anal-   │  │   (cache /     │
│   yses, sess.)  │  │    optional)   │
│   port 5432     │  │   port 6379    │
└─────────────────┘  └────────────────┘
        ▲
        │ kubeconfig mount
┌───────┴──────────────────┐
│  Kubernetes Cluster      │
│  (kubectl + kubeconfig)  │
└──────────────────────────┘
```

### Container Map (Docker Compose)

| Container | Image | Host Port | Internal Port |
|---|---|---|---|
| `k8s-log-analytics-frontend` | Custom (Nginx) | **8080** | 80 |
| `k8s-log-analytics-backend` | Custom (Python 3.11) | **8000** | 8000 |
| `k8s-log-analytics-db` | postgres:15-alpine | 5432 | 5432 |
| `k8s-log-analytics-redis` | redis:7-alpine | — | 6379 |

---

## Tech Stack

**Backend** — Python 3.11, FastAPI, SQLAlchemy 2, PostgreSQL, Azure OpenAI SDK, `kubectl` subprocess

**Frontend** — React 18, TypeScript, Vite, Tailwind CSS, Recharts, React Router, Lucide Icons

**Infrastructure** — Docker, Docker Compose, Nginx (frontend static serving + proxy)

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- Azure OpenAI resource with a deployed model *(optional — fallback analyser works without it)*
- `kubectl` configured with a valid `kubeconfig` *(optional — required only for live cluster browsing)*

---

## Quick Start (Docker — recommended)

### 1. Clone the repo

```bash
git clone <repo-url>
cd Log_Analyzer
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
# Azure OpenAI  (leave blank to use rule-based fallback)
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT=gpt-5.4
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# Optional overrides
AZURE_OPENAI_TEMPERATURE=0.1
AZURE_OPENAI_MAX_TOKENS=100000
```

### 3. Build and run

```bash
docker compose up -d --build
```

### 4. Open the app

| Service | URL |
|---|---|
| **Frontend** | http://localhost:8080 |
| **Backend API** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/docs |
| **Health check** | http://localhost:8000/health |

### 5. Stop

```bash
docker compose down
# To also remove volumes (wipes the database):
docker compose down -v
```

---

## Local Development Setup

### Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# Set env vars (or create a .env in backend/)
set AZURE_OPENAI_ENDPOINT=...
set AZURE_OPENAI_API_KEY=...
set DATABASE_URL=sqlite:///./logs.db   # use SQLite for local dev

uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # starts on http://localhost:5173
```

> The Vite dev server proxies `/api` to `http://localhost:8000` automatically.

---

## Kubernetes Cluster Access

The backend mounts your local `~/.kube/config` into the container read-only:

```yaml
volumes:
  - ~/.kube/config:/kubeconfig/config:ro
```

**Docker Desktop Kubernetes** (built-in cluster) works out of the box.
For a remote cluster, make sure `kubectl get nodes` succeeds on your host before starting containers.

To disable cluster features entirely, remove the `KUBECONFIG` env var from `docker-compose.yml`.

---

## Project Structure

```
Log_Analyzer/
├── docker-compose.yml
├── .env                        # your secrets (not committed)
├── README.md
├── docs/                       # supplementary notes and fix logs
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI app, CORS, router registration
│       ├── api/
│       │   ├── logs.py         # upload, analyze, job polling, sessions
│       │   └── kubernetes.py   # namespace, pod, log endpoints
│       ├── core/
│       │   ├── config.py       # Pydantic settings (reads .env)
│       │   └── database.py     # SQLAlchemy engine + session factory
│       ├── models/
│       │   ├── log.py          # ORM models: LogEntry, K8sResource, LogAnalysis, LogSession
│       │   └── schemas.py      # Pydantic request/response schemas
│       └── services/
│           ├── log_parser.py   # Regex-based multi-format log parser
│           ├── k8s_collector.py# kubectl subprocess wrapper
│           └── llm_analyzer.py # LLM analysis, context condensation, fallback
│
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── index.html
    └── src/
        ├── App.tsx             # App shell, nav, live status bar
        ├── context/
        │   └── AnalysisContext.tsx  # Global async job tracker
        ├── pages/
        │   ├── UploadPage.tsx
        │   ├── ClusterBrowserPage.tsx
        │   └── DashboardPage.tsx
        ├── services/
        │   └── api.ts          # Typed API client
        └── types/
            └── index.ts
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | No | — | Azure OpenAI resource endpoint |
| `AZURE_OPENAI_API_KEY` | No | — | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | No | `gpt-5.4` | Deployed model name |
| `AZURE_OPENAI_API_VERSION` | No | `2024-12-01-preview` | API version |
| `DATABASE_URL` | Yes | `sqlite:///./logs.db` | SQLAlchemy DB URL |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis URL |
| `KUBECONFIG` | No | — | Path to kubeconfig inside container |
| `LOG_RETENTION_DAYS` | No | `30` | Days before log cleanup |

---

## API Quick Reference

```
GET  /health                              → liveness check
GET  /docs                                → Swagger UI

POST /api/logs/upload                     → upload .log file
POST /api/logs/analyze                    → start async analysis job → { job_id }
GET  /api/logs/jobs/{job_id}              → poll job status + result
GET  /api/logs/sessions                   → list all saved sessions
GET  /api/logs/entries/{resource_id}      → paginated log entries

GET  /api/k8s/health                      → cluster health summary
GET  /api/k8s/namespaces                  → list namespaces
GET  /api/k8s/pods/{namespace}            → list pods
GET  /api/k8s/logs/{namespace}/{pod}      → fetch + optionally store pod logs
```

---

## Supplementary Docs

All implementation notes, fix logs, and migration guides are in [`docs/`](docs/).