# Setup and Testing Guide

## Quick Start

### Prerequisites Verification

Ensure you have the following installed:
- Docker Desktop (with Kubernetes enabled)
- Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for local development)

### Installation Steps

1. **Navigate to the project directory**
   ```bash
   cd k8s-log-analytics
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your GEMINI_API_KEY (optional)
   ```

3. **Start the application**
   ```bash
   # On Windows
   start.bat
   
   # On Linux/Mac
   chmod +x start.sh
   ./start.sh
   
   # Or manually with Docker Compose
   docker compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:8080
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Testing the Application

### 1. Test Backend Health

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status":"healthy"}
```

### 2. Test API Endpoints

```bash
# Test root endpoint
curl http://localhost:8000/

# Test cluster health (requires K8s access)
curl http://localhost:8000/api/k8s/health

# Test namespaces (requires K8s access)
curl http://localhost:8000/api/k8s/namespaces
```

### 3. Test File Upload

Create a test log file:
```bash
cat > test.log << EOF
2024-01-15T10:30:45.123Z [INFO] Application started successfully
2024-01-15T10:30:46.456Z [INFO] Database connection established
2024-01-15T10:31:15.789Z [ERROR] Failed to process request: Connection timeout
2024-01-15T10:31:20.012Z [WARNING] Memory usage above 80%
2024-01-15T10:32:00.345Z [INFO] Request processed successfully
EOF
```

Upload the file:
```bash
curl -X POST -F "file=@test.log" http://localhost:8000/api/logs/upload
```

### 4. Test Log Retrieval

```bash
# Get all log entries
curl http://localhost:8000/api/logs/entries

# Get entries by level
curl "http://localhost:8000/api/logs/entries?level=ERROR"

# Get resources
curl http://localhost:8000/api/logs/resources
```

### 5. Test Frontend

1. Open http://localhost in your browser
2. Navigate to the **Upload** tab
3. Upload the test.log file
4. View the analysis results
5. Navigate to the **Cluster** tab (if K8s is configured)
6. Navigate to the **Dashboard** tab to view metrics

## Manual Testing Checklist

### Backend Testing
- [ ] Health check endpoint responds correctly
- [ ] File upload accepts .log and .txt files
- [ ] Log parsing extracts timestamps and levels correctly
- [ ] Database stores log entries
- [ ] LLM analysis provides meaningful results (with API key)
- [ ] Fallback analysis works without API key
- [ ] Kubernetes integration retrieves pod logs (if configured)
- [ ] API documentation is accessible

### Frontend Testing
- [ ] Application loads without errors
- [ ] File upload interface works
- [ ] Analysis results display correctly
- [ ] Cluster browser shows namespaces and pods (if K8s configured)
- [ ] Dashboard displays metrics and charts
- [ ] Filters work correctly
- [ ] Navigation between pages works
- [ ] Responsive design works on different screen sizes

### Integration Testing
- [ ] Frontend can communicate with backend
- [ ] File upload triggers analysis
- [ ] Cluster logs can be retrieved and analyzed
- [ ] Real-time filtering works
- [ ] Data persists in database

## Troubleshooting

### Docker Build Issues

If the Docker build fails:

1. **Check Docker is running**
   ```bash
   docker --version
   docker ps
   ```

2. **Clean up and rebuild**
   ```bash
   docker compose down -v
   docker system prune -a
   docker compose build --no-cache
   docker compose up -d
   ```

3. **Check build logs**
   ```bash
   docker compose logs backend
   docker compose logs frontend
   ```

### Database Connection Issues

If the backend can't connect to the database:

1. **Check PostgreSQL is running**
   ```bash
   docker compose ps postgres
   docker compose logs postgres
   ```

2. **Test database connection**
   ```bash
   docker exec -it k8s-log-analytics-db psql -U loguser -d loganalytics -c "SELECT 1;"
   ```

3. **Check environment variables**
   ```bash
   docker compose exec backend env | grep DATABASE
   ```

### Kubernetes Integration Issues

If cluster integration doesn't work:

1. **Verify kubeconfig is mounted**
   ```bash
   docker exec k8s-log-analytics-backend ls -la /kubeconfig/
   ```

2. **Test kubectl access from container**
   ```bash
   docker exec -it k8s-log-analytics-backend kubectl get pods
   ```

3. **Check permissions**
   - Ensure the kubeconfig has appropriate permissions
   - Verify RBAC rules allow pod log access

### Port Conflicts

If ports are already in use:

1. **Check what's using the ports**
   ```bash
   # Windows
   netstat -ano | findstr :80
   netstat -ano | findstr :8000
   
   # Linux/Mac
   lsof -i :80
   lsof -i :8000
   ```

2. **Change ports in docker-compose.yml**
   ```yaml
   services:
     frontend:
       ports:
         - "8080:80"  # Change from 80 to 8080
     backend:
       ports:
         - "8001:8000"  # Change from 8000 to 8001
   ```

### Gemini API Issues

If LLM analysis doesn't work:

1. **Verify API key is set**
   ```bash
   docker exec k8s-log-analytics-backend env | grep GEMINI
   ```

2. **Test API key manually**
   ```bash
   curl https://generativelanguage.googleapis.com/v1/models?key=YOUR_API_KEY
   ```

3. **Check API quota and billing**
   - Ensure your Google Cloud project has API access enabled
   - Check Gemini API usage limits
   - Check API usage limits

## Development Mode

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

## Production Deployment

### Environment Variables

Set these in your production environment:

```env
DATABASE_URL=postgresql://user:pass@production-db:5432/loganalytics
REDIS_URL=redis://production-redis:6379/0
OPENAI_API_KEY=your-production-api-key
SECRET_KEY=your-secret-key
LOG_RETENTION_DAYS=30
```

### Security Considerations

1. **Change default passwords** in docker-compose.yml
2. **Use HTTPS** with a reverse proxy (nginx/traefik)
3. **Implement authentication** (OAuth2, JWT)
4. **Restrict Kubernetes access** with RBAC
5. **Enable rate limiting** on API endpoints
6. **Use secrets management** (HashiCorp Vault, AWS Secrets Manager)

### Scaling

1. **Database scaling**
   - Use managed PostgreSQL (RDS, Cloud SQL)
   - Enable connection pooling
   - Set up read replicas

2. **Backend scaling**
   - Deploy multiple backend instances
   - Use load balancer
   - Implement horizontal pod autoscaling

3. **Frontend scaling**
   - Use CDN for static assets
   - Enable caching
   - Deploy multiple instances

## Monitoring

### Application Monitoring

1. **Health checks**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Log aggregation**
   ```bash
   docker compose logs -f backend
   docker compose logs -f frontend
   ```

3. **Metrics collection**
   - Add Prometheus metrics
   - Set up Grafana dashboards
   - Monitor resource usage

### Performance Monitoring

1. **Database performance**
   ```bash
   docker exec -it k8s-log-analytics-db psql -U loguser -d loganalytics
   SELECT * FROM pg_stat_activity;
   ```

2. **API response times**
   - Add timing middleware
   - Monitor with APM tools
   - Set up alerting

## Backup and Recovery

### Database Backup

```bash
# Backup
docker exec k8s-log-analytics-db pg_dump -U loguser loganalytics > backup.sql

# Restore
docker exec -i k8s-log-analytics-db psql -U loguser loganalytics < backup.sql
```

### Volume Backup

```bash
# Backup volumes
docker run --rm -v k8s-log-analytics_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres-backup.tar.gz /data
```

## Support

For issues:
1. Check the logs: `docker compose logs -f`
2. Review this troubleshooting guide
3. Check the main README.md
4. Create an issue in the repository
