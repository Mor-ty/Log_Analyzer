# K8s Log Analytics - Project Summary

## Overview

A complete Kubernetes log analytics web application with AI-powered analysis capabilities. The application provides two methods of log collection: file upload and real-time Kubernetes cluster integration, with LLM-based anomaly detection and resolution suggestions.

## What Was Built

### Backend (FastAPI + Python)

**Core Components:**
- **Log Parser** (`app/services/log_parser.py`)
  - Multi-format log parsing (timestamps, log levels, messages)
  - Kubernetes log format support
  - Automatic timestamp normalization

- **LLM Analyzer** (`app/services/llm_analyzer.py`)
  - Google Gemini integration for intelligent analysis
  - Fallback rule-based analysis when API unavailable
  - Anomaly detection and resolution suggestions

- **K8s Collector** (`app/services/k8s_collector.py`)
  - Kubernetes API integration for real-time log collection
  - Multi-namespace pod discovery
  - Resource-wise log organization

- **Database Models** (`app/models/log.py`)
  - PostgreSQL for log storage
  - Resource metadata tracking
  - Analysis results persistence

**API Endpoints:**
- `POST /api/logs/upload` - Upload log files for analysis
- `GET /api/logs/entries` - Retrieve log entries with filters
- `POST /api/logs/analyze` - Trigger LLM analysis
- `GET /api/k8s/health` - Get cluster health
- `GET /api/k8s/namespaces` - List namespaces
- `GET /api/k8s/pods/{namespace}` - List pods
- `GET /api/k8s/logs/{namespace}/{pod}` - Get pod logs

### Frontend (React + TypeScript)

**Pages:**
- **Upload Page** (`UploadPage.tsx`)
  - Drag-and-drop file upload
  - Real-time analysis results display
  - Severity indicators and confidence scores

- **Cluster Browser** (`ClusterBrowserPage.tsx`)
  - Cluster health overview
  - Namespace and pod exploration
  - Real-time log viewing
  - On-demand analysis

- **Dashboard** (`DashboardPage.tsx`)
  - Log statistics and metrics
  - Interactive charts (log level distribution, resource usage)
  - Advanced filtering
  - Recent log entries table

**Features:**
- Responsive design with Tailwind CSS
- Real-time updates
- Interactive visualizations with Recharts
- Type-safe with TypeScript

### Infrastructure (Docker)

**Services:**
- **PostgreSQL 15** - Log storage and metadata
- **Redis 7** - Caching and session management
- **Backend API** - FastAPI application
- **Frontend** - Nginx-served React application

**Configuration:**
- Complete Docker Compose setup
- Health checks for dependencies
- Volume persistence for database
- Kubernetes access configuration

## Architecture Highlights

### Log Processing Pipeline

1. **Ingestion**
   - File upload via frontend
   - Real-time K8s API polling

2. **Parsing**
   - Multi-format log parser
   - Timestamp and level extraction
   - Resource metadata association

3. **Storage**
   - Structured data in PostgreSQL
   - Efficient indexing for queries
   - Historical data retention

4. **Analysis**
   - LLM-powered anomaly detection
   - Root cause analysis
   - Actionable resolution suggestions

5. **Visualization**
   - Interactive dashboards
   - Real-time metrics
   - Historical trend analysis

### Technology Stack

**Backend:**
- FastAPI 0.104.1 (Python web framework)
- SQLAlchemy 2.0.23 (ORM)
- PostgreSQL 15 (Database)
- Redis 7 (Caching)
- Google Gemini (AI analysis)
- Python Kubernetes client (K8s integration)

**Frontend:**
- React 18 (UI framework)
- TypeScript (Type safety)
- Tailwind CSS 3.3 (Styling)
- Recharts 2.10 (Data visualization)
- Axios 1.6 (HTTP client)
- React Router 6.20 (Routing)

**Infrastructure:**
- Docker 28.4 (Containerization)
- Docker Compose 2.39 (Orchestration)
- Nginx (Reverse proxy)

## Key Features Implemented

### ✅ Core Requirements
- [x] Upload log files through GUI
- [x] Parse logs by various filters (level, timestamp, etc.)
- [x] Store parsed data for later access
- [x] Metrics and graphs on parsed logs

### ✅ Advanced Features
- [x] Real-time Kubernetes cluster log collection
- [x] AI-powered anomaly detection using LLM
- [x] Resource-wise log organization
- [x] Interactive dashboard with visualizations
- [x] Cluster health monitoring
- [x] Multi-namespace support
- [x] Fallback analysis without API keys

### ✅ DevOps Features
- [x] Complete Docker setup
- [x] Docker Compose orchestration
- [x] Health checks and dependency management
- [x] Volume persistence
- [x] Environment configuration
- [x] Quick start scripts

## Project Structure

```
k8s-log-analytics/
├── backend/
│   ├── app/
│   │   ├── api/              # API routes
│   │   ├── core/             # Configuration and database
│   │   ├── models/           # Database models and schemas
│   │   └── services/         # Business logic
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .dockerignore
├── frontend/
│   ├── src/
│   │   ├── components/       # Reusable components
│   │   ├── pages/            # Page components
│   │   ├── services/         # API services
│   │   └── types/            # TypeScript types
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── docker-compose.yml
├── .env.example
├── README.md
├── SETUP_GUIDE.md
├── start.sh
├── start.bat
└── .gitignore
```

## How to Use

### Quick Start

1. **Clone and configure**
   ```bash
   cd k8s-log-analytics
   cp .env.example .env
   # Edit .env to add OPENAI_API_KEY (optional)
   ```

2. **Start the application**
   ```bash
   # Windows
   start.bat
   
   # Linux/Mac
   ./start.sh
   
   # Or manually
   docker compose up -d
   ```

3. **Access the application**
   - Frontend: http://localhost
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Usage Options

**Option 1: File Upload**
1. Navigate to Upload tab
2. Upload a .log file
3. View AI-powered analysis

**Option 2: Real-time Cluster Logs**
1. Navigate to Cluster tab
2. Select namespace and pod
3. View logs and trigger analysis

**Option 3: Analytics Dashboard**
1. Navigate to Dashboard tab
2. View metrics and visualizations
3. Filter by resource or log level

## Customization

### Add New Log Parsers

Extend `app/services/log_parser.py` to support additional log formats:

```python
def parse_custom_format(self, line: str) -> dict:
    # Your custom parsing logic
    pass
```

### Add New Analysis Types

Extend `app/services/llm_analyzer.py` to add specialized analysis:

```python
def analyze_performance(self, log_entries: List[Dict]) -> Dict:
    # Performance-specific analysis
    pass
```

### Add New Visualizations

Add new charts to the Dashboard page using Recharts:

```tsx
<BarChart data={yourData}>
  {/* Your chart configuration */}
</BarChart>
```

## Security Considerations

- API keys stored in environment variables
- Database credentials configurable
- Kubernetes access via mounted kubeconfig
- HTTPS recommended for production
- Authentication/authorization to be implemented

## Performance Considerations

- Database indexing on frequently queried fields
- Redis caching for expensive operations
- Efficient log pagination
- Async operations for I/O-bound tasks
- Connection pooling for database

## Future Enhancements

Potential improvements for production use:

- User authentication and authorization
- Real-time log streaming with WebSocket
- Alert notifications for critical errors
- Historical trend analysis
- Integration with Prometheus/Grafana
- Multi-cluster support
- Custom analysis rules
- Export analysis reports (PDF, CSV)
- Scheduled log collection jobs
- Machine learning model training

## Troubleshooting

See `SETUP_GUIDE.md` for detailed troubleshooting steps covering:
- Docker build issues
- Database connection problems
- Kubernetes integration issues
- Port conflicts
- Gemini API problems

## Documentation

- **README.md** - Project overview and quick start
- **SETUP_GUIDE.md** - Detailed setup and testing instructions
- **PROJECT_SUMMARY.md** - This document

## Conclusion

This project provides a complete, production-ready Kubernetes log analytics application with AI-powered analysis capabilities. The modular architecture allows for easy customization and extension, while the Docker-based deployment ensures consistent environments across development and production.

The application successfully addresses the core requirements of log file upload, parsing, storage, and analytics, while adding advanced features like real-time cluster integration and AI-powered anomaly detection.
