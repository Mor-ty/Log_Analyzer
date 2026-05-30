# 5-Minute Demo Walkthrough Script
## K8s Log Analytics — Cognition AI Support Engineer Assignment

---

## [0:00 – 0:30] Hook + Project Intro

> "Hey — I built a Kubernetes Log Analytics platform for the Cognition AI Support Engineer
> assignment. It's a full-stack, Dockerized web app that takes raw log files or live K8s pod
> logs, runs them through an AI analysis pipeline, and gives you structured diagnostics —
> anomalies, root causes, kubectl remediation commands, severity scoring — all in a clean
> SaaS-style dashboard.
>
> The stack: FastAPI backend, React + TypeScript frontend, SQLite for persistence, and
> Azure OpenAI for the LLM brain. Everything runs in Docker Compose with a single command.
> Let me walk you through how it works."

**[ACTION]** Show the running app in the browser at localhost:3000.

---

## [0:30 – 1:15] Architecture Overview

> "Two containers — backend on port 8000, frontend on port 3000, talking through a shared
> Docker network. The backend is a FastAPI app structured in layers: `api/` handles routing,
> `services/` holds all business logic — log parsing, K8s collection, LLM analysis — and
> `models/` defines the database schema with SQLAlchemy.
>
> The frontend is a Vite + React + Tailwind app with three pages: Upload, Cluster Browser,
> and Dashboard."

**[ACTION]** Show `docker-compose.yml` briefly, then the project tree in the IDE.

---

## [1:15 – 2:00] K8s Cluster Connection

> "The Cluster Browser connects to your live Kubernetes cluster through kubectl — no SDK
> dependency, just subprocess calls. On startup, `k8s_collector.py` probes
> `kubectl version --client` to detect availability. If kubectl is configured with a valid
> kubeconfig, it starts firing commands: `kubectl get namespaces`, `kubectl get pods -n
> <namespace>`, `kubectl logs <pod>`.
>
> There's a smart `store` flag on the logs endpoint. When you browse logs, store is false —
> view-only, nothing written to the database. Only when you explicitly trigger analysis does
> store flip to true, persisting the pod, its log entries, and the analysis result. This avoids
> bloating the DB on every page load."

**[ACTION]** Show `backend/app/services/k8s_collector.py` — highlight `_check_kubectl_available`
and `_run_kubectl_command`. Then show the Cluster Browser page in the UI.

---

## [2:00 – 3:00] Async Analysis Pipeline

> "LLM calls are slow — they can take 10 to 30 seconds. I didn't want to block the HTTP
> request. So analysis is fully asynchronous using a ThreadPoolExecutor with 4 workers.
>
> When you click Analyze, the API immediately returns a job_id. The actual LLM work runs
> in a background thread with its own SQLAlchemy session — no shared state conflict.
>
> The frontend polls `GET /api/logs/jobs/{job_id}` every few seconds. This is tracked
> globally in React via an AnalysisContext — so you can navigate freely between pages while
> the job runs. The status bar at the top shows live elapsed time and a spinner. When the
> job completes, the result is written to the DB and a session record is auto-created."

**[ACTION]** Show `backend/app/api/logs.py` — highlight `_executor = ThreadPoolExecutor(max_workers=4)`,
the `_jobs` dict, and `_run_analysis_job`. Then show `frontend/src/context/AnalysisContext.tsx`
briefly. Trigger a live analysis so the polling status bar is visible.

---

## [3:00 – 3:50] LLM Optimization — Smart Context Condensation

> "The biggest LLM engineering challenge: a log file can have 10,000 lines but an LLM
> context window is finite and expensive. So I wrote a smart condensation layer in
> `_prepare_condensed_context`.
>
> Instead of dumping raw lines, I normalize each message — stripping timestamps, hex IDs,
> and numbers — then group identical patterns together and send `[47x] OOMKilled` instead
> of 47 identical lines. This cuts token usage by up to 90% and gives the LLM a frequency
> signal it wouldn't get from raw text. The most repeated patterns surface first.
>
> The prompt itself is tightly engineered — it instructs the model to extract real pod and
> namespace names directly from `/var/log/pods/` paths in the logs, never invent names, and
> anchor every finding to specific log evidence. Output is strict JSON.
>
> If the confidence score in the response is below 0.4, we automatically fall back to a
> pattern-aware rule-based analyzer that handles CrashLoopBackOff, OOMKilled,
> ImagePullBackOff, and scheduling failures — no LLM required."

**[ACTION]** Show `backend/app/services/llm_analyzer.py` — scroll through
`_prepare_condensed_context`, then `_build_smart_prompt`, then `_enhanced_fallback_analysis`.

---

## [3:50 – 4:30] Session Handling & Dashboard

> "Every completed analysis auto-creates a LogSession record linking the resource, the
> analysis result, entry count, and severity. On the Dashboard, sessions are grouped by
> resource name and sorted newest-first. You can expand any group to see every individual
> run — if you analyzed the same pod three times, you see all three with timestamps and
> severities.
>
> From any session you can restore the full analysis inline without re-running the LLM —
> it just reads from the database. The charts — a pie chart for log level distribution and a
> bar chart for top resources — are built with Recharts and update reactively when you
> select a session."

**[ACTION]** Show the Dashboard page. Click a session group to expand it, then click the
brain icon to restore an analysis. Point out the pie and bar charts.

---

## [4:30 – 5:00] GitHub Copilot + Closing

> "I built this entire project using GitHub Copilot's agent mode inside VS Code. The biggest
> time saves: scaffolding the entire FastAPI and React structure in one shot, fixing the async
> job pattern when I hit SQLAlchemy session threading issues, debugging TypeScript errors
> during the Docker build, and iterating on the LLM prompt until the structured JSON output
> was reliable.
>
> What would have taken days of back-and-forth — the condensed context algorithm, the
> async polling system, the session grouping UI — Copilot let me go from concept to working
> code fast, with me steering the architecture and the AI handling the boilerplate.
>
> The whole thing runs with one command: `docker compose up`. Upload a log, hit Analyze,
> and in under 30 seconds you get actionable kubectl commands with your real pod names.
> That's the product. Thanks for watching."

**[ACTION]** Run `docker compose up -d` in the terminal. Show the containers starting. End on
the Upload page with an analysis result visible.

---

## Timing Cheatsheet

| Section                        | Start  | End    | Duration |
|-------------------------------|--------|--------|----------|
| Hook + Intro                  | 0:00   | 0:30   | 30s      |
| Architecture Overview         | 0:30   | 1:15   | 45s      |
| K8s Cluster Connection        | 1:15   | 2:00   | 45s      |
| Async Analysis Pipeline       | 2:00   | 3:00   | 60s      |
| LLM Optimization              | 3:00   | 3:50   | 50s      |
| Session Handling & Dashboard  | 3:50   | 4:30   | 40s      |
| Copilot + Closing             | 4:30   | 5:00   | 30s      |

---

## Pre-Recording Checklist

- [ ] `docker compose up -d` — both containers healthy
- [ ] Pre-upload `test_error_log.txt` so an analysis result is already cached
- [ ] Browser at `localhost:3000`, DevTools closed, zoom at 125%
- [ ] IDE open to `llm_analyzer.py` — ready to scroll to `_prepare_condensed_context`
- [ ] Terminal open at project root
- [ ] Mic check — no background noise
- [ ] Record at 1080p minimum
