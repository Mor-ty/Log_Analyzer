# Frontend Port Change Fix

## Issue
The frontend was not accessible at `localhost:80` despite the container running successfully.

### Symptoms
- Backend accessible at `localhost:8000` ✅
- Frontend container running ✅
- Frontend not accessible at `localhost:80` ❌
- Docker showed port mapping as `80/tcp` instead of `0.0.0.0:80->80/tcp`

## Root Cause
Port 80 was blocked or conflicting on Windows, preventing Docker Desktop from mapping the port properly. Port 80 is commonly used by:
- IIS (Internet Information Services) on Windows
- Other web services
- System processes

## Solution Applied
Changed the frontend port mapping from port 80 to port 8080 to avoid conflicts.

### Docker Compose Configuration
**File**: `docker-compose.yml`

```yaml
# Before
ports:
  - "80:80"

# After
ports:
  - "8080:80"
```

## Verification
After the change, Docker properly shows the port mapping:
```
0.0.0.0:8080->80/tcp
```

## Updated Access Information

### Application Endpoints
- **Frontend**: http://localhost:8080 (changed from :80)
- **Backend API**: http://localhost:8000 (unchanged)
- **API Documentation**: http://localhost:8000/docs (unchanged)
- **Health Check**: http://localhost:8000/health (unchanged)

### Service Ports
- PostgreSQL: 5432 (unchanged)
- Redis: 6379 (unchanged)
- Backend API: 8000 (unchanged)
- Frontend: 8080 (changed from 80)

## Internal Configuration
No changes needed to nginx configuration since:
- Nginx still listens on port 80 inside the container
- Docker maps host port 8080 to container port 80
- API proxy configuration remains unchanged

## Testing
You can now access the application at:
- Open browser to: **http://localhost:8080**
- The React application should load successfully
- API calls will be proxied through nginx to the backend

## Alternative Ports
If port 8080 also conflicts, you can change to other available ports:
- 3000 (common for Node.js apps)
- 8081, 8082, etc.
- 5173 (Vite default)

To change the port, update `docker-compose.yml`:
```yaml
ports:
  - "3000:80"  # or any other available port
```

## Troubleshooting Port Conflicts

### Check Port Availability
```bash
# Windows
netstat -ano | findstr :8080

# Linux/Mac
lsof -i :8080
```

### Common Port Conflicts on Windows
- 80: IIS, other web servers
- 443: HTTPS services
- 3000: Some Node.js applications
- 8080: Often used as alternative HTTP port
- 5173: Vite dev server

## Rollback
If you need to use port 80, you must:
1. Stop conflicting services (IIS, etc.)
2. Run Docker Desktop as administrator
3. Restart Docker Desktop
4. Rebuild the containers

However, using port 8080 is recommended for Windows environments.

## Documentation Updates
The following documentation should be updated to reflect the new port:
- README.md (quick start section)
- SETUP_GUIDE.md (access information)
- Any other references to port 80 for the frontend

## Impact on Users
Users need to:
1. Use http://localhost:8080 instead of http://localhost
2. Update any bookmarks or saved URLs
3. Update any configuration that references port 80

The change is minimal and only affects the external access port, not the internal application configuration.
