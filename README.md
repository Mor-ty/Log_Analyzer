# K8s Log Analytics

A web application for analyzing Kubernetes cluster logs using AI-powered anomaly detection and LLM-based analysis.

## Features

- **File Upload**: Upload log files through the GUI for immediate analysis
- **Real-time Collection**: Collect logs directly from your Kubernetes cluster
- **AI-Powered Analysis**: LLM-based anomaly detection and resolution suggestions
- **Interactive Dashboard**: Visualize log metrics, errors, and trends
- **Resource Browser**: Browse logs by namespace, pod, and container
- **Smart Filtering**: Filter logs by level, timestamp, and resource
- **Storage**: Persistent log storage with PostgreSQL

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React + TypeScript)            │
│  - File upload interface                                     │
│  - Real-time log browser (namespace/pod/service selection)  │
│  - Analysis results dashboard                                │
│  - Filters (log level, timestamp, keywords)                 │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/WebSocket
┌────────────────────────▼────────────────────────────────────┐
│              Backend API (FastAPI + Python)                  │
│  - /api/upload-log - File upload endpoint                   │
│  - /api/logs/{namespace}/{pod} - Fetch stored logs          │
│  - /api/analyze - Trigger LLM analysis                      │
│  - /api/resources - List K8s resources                      │
│  - Background task: Log collector (polls K8s API)          │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
┌────────▼────────┐ ┌───▼────────┐ ┌────▼────────────┐
│  PostgreSQL     │ │  Redis   │ │  LLM API        │
│  (Parsed logs) │ │  (Cache)  │ │  (Gemini AI)    │
└─────────────────┘ └────────────┘ └─────────────────┘
```

## Prerequisites

- Docker and Docker Compose
- Kubernetes cluster (for real-time log collection)
- Google Gemini API Key (optional, for AI-powered analysis)
- kubectl configured (for cluster access)

## Quick Start

### 1. Clone the Repository

```bash
cd k8s-log-analytics
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add your Google Gemini API key:

```env
GEMINI_API_KEY=your-actual-api-key-here
```

> **Note**: For detailed instructions on getting your Gemini API key, see [GEMINI_SETUP.md](GEMINI_SETUP.md)

### 3. Start the Application

```bash
docker-compose up -d
```

This will start:
- PostgreSQL database (port 5432)
- Redis cache (port 6379)
- Backend API (port 8000)
- Frontend web interface (port 8080)

### 4. Access the Application

Open your browser and navigate to: `http://localhost:8080`

## Usage

### Upload Log Files

1. Navigate to the **Upload** tab
2. Click to select a log file (.log, .txt)
3. Click "Upload & Analyze"
4. View AI-powered analysis results

### Browse Cluster Logs

1. Navigate to the **Cluster** tab
2. View cluster health overview
3. Select a namespace
4. Expand a pod to view logs
5. Click "Analyze" for AI-powered insights

### View Analytics Dashboard

1. Navigate to the **Dashboard** tab
2. View log statistics and metrics
3. Filter by resource or log level
4. Explore visualizations

## API Documentation

Once the application is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Key Endpoints

- `POST /api/logs/upload` - Upload a log file for analysis
- `GET /api/logs/entries` - Retrieve log entries with filters
- `POST /api/logs/analyze` - Trigger LLM analysis
- `GET /api/k8s/health` - Get cluster health
- `GET /api/k8s/pods/{namespace}` - List pods in namespace
- `GET /api/k8s/logs/{namespace}/{pod}` - Get pod logs

## Configuration

### Backend Configuration

Edit `backend/.env`:

```env
DATABASE_URL=postgresql://loguser:logpass@postgres:5432/loganalytics
REDIS_URL=redis://redis:6379/0
GEMINI_API_KEY=your-gemini-api-key
KUBECONFIG=/path/to/kubeconfig
LOG_RETENTION_DAYS=30
```

### Kubernetes Access

For real-time log collection, ensure:

1. Your kubeconfig is mounted in the backend container
2. The backend has permissions to access pod logs
3. ServiceAccount with appropriate RBAC is configured

### Without Gemini API

The application includes a fallback rule-based analysis when Gemini is not configured. It will still provide:
- Basic error counting
- Common error pattern detection
- Generic troubleshooting suggestions

## Development

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## Docker Commands

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild after changes
docker-compose up -d --build

# Remove all data (including database)
docker-compose down -v
```

## Troubleshooting

### Backend fails to start

- Check database connection: `docker-compose logs postgres`
- Verify environment variables in `.env`
- Check for port conflicts

### Cannot connect to Kubernetes cluster

- Ensure kubeconfig is mounted correctly
- Verify cluster connectivity from within container
- Check RBAC permissions

### Frontend shows connection errors

- Ensure backend is running: `docker-compose ps`
- Check API proxy configuration in nginx
- Verify CORS settings

### Gemini analysis fails

- Verify API key is set correctly
- Check Gemini API quota and billing
- Review backend logs for specific errors

## Architecture Details

### Log Processing Pipeline

1. **Ingestion**: Logs are collected via file upload or K8s API
2. **Parsing**: Log parser extracts timestamp, level, and message
3. **Storage**: Parsed logs stored in PostgreSQL
4. **Analysis**: LLM analyzes logs for anomalies and patterns
5. **Visualization**: Results displayed in dashboard

### Technology Stack

- **Frontend**: React 18, TypeScript, Tailwind CSS, Recharts
- **Backend**: FastAPI, Python 3.11, SQLAlchemy
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **AI**: Google Gemini (optional)
- **Container**: Docker, Docker Compose
- **Orchestration**: Kubernetes API client

## Security Considerations

- Store API keys in environment variables
- Use HTTPS in production
- Implement authentication/authorization
- Restrict Kubernetes access with RBAC
- Regular security updates for dependencies

## Future Enhancements

- [ ] User authentication and authorization
- [ ] Real-time log streaming with WebSocket
- [ ] Alert notifications for critical errors
- [ ] Historical trend analysis
- [ ] Integration with Prometheus/Grafana
- [ ] Multi-cluster support
- [ ] Custom analysis rules
- [ ] Export analysis reports

## License

MIT License

## Support

For issues and questions:
- Create an issue in the repository
- Check existing documentation
- Review API docs at `/docs` endpoint

## Acknowledgments

- Built with FastAPI and React
- Powered by OpenAI GPT-4 for analysis
- Kubernetes client for cluster integration
