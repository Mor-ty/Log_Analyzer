# Docker Build Error Fix

## Issue
The Docker build failed with the following error:
```
ERROR: Could not find a version that satisfies the requirement python-kubernetes==28.1.0 (from versions: 0.1, 0.2)
ERROR: No matching distribution found for python-kubernetes==28.1.0
```

## Root Cause
The package name `python-kubernetes` is incorrect. The official package name for the Kubernetes Python client is simply `kubernetes`. Additionally, the version 28.1.0 may not have existed or was incorrectly specified.

## Solution
Updated `backend/requirements.txt` with the following changes:

### Changed Package Name
- ❌ `python-kubernetes==28.1.0`
- ✅ `kubernetes==29.0.0`

### Updated Versions for Better Compatibility
- `alembic==1.12.1` → `alembic==1.13.1`
- `pydantic==2.5.0` → `pydantic==2.5.3`
- `google-generativeai==0.3.2` → `google-generativeai==0.8.3`
- `celery==5.3.4` → `celery==5.3.6`

### Final Requirements
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.13.1
pydantic==2.5.3
pydantic-settings==2.1.0
python-multipart==0.0.6
kubernetes==29.0.0
google-generativeai==0.8.3
python-dotenv==1.0.0
httpx==0.25.2
celery==5.3.6
redis==5.0.1
```

## Verification
The corrected package name `kubernetes` is the official Python client for Kubernetes:
- Official repository: https://github.com/kubernetes-client/python
- PyPI package: https://pypi.org/project/kubernetes/

## Next Steps
1. The Docker build should now work with the corrected requirements
2. Run `docker compose build backend` to verify the fix
3. If issues persist, consider using `>=` version constraints for more flexibility

## Alternative Approach
If you encounter version compatibility issues, you can use version ranges:
```
kubernetes>=28.0.0,<30.0.0
google-generativeai>=0.3.0
```

This allows pip to find compatible versions within the specified range.
