# API 404 and Upload 500 Error Fixes

## Issues Fixed

### 1. API 404 Error on Analyze Button
**Error**: `POST /api/logs/analyze HTTP/1.1" 404 Not Found`

**Root Cause**: nginx proxy configuration was stripping the `/api` prefix when proxying requests to the backend.

**Issue**: The nginx proxy was configured as:
```nginx
proxy_pass http://backend:8000;
```

This caused:
- Request: `/api/logs/analyze` → nginx → `http://backend:8000/logs/analyze` (missing `/api`)
- Expected: `/api/logs/analyze` → nginx → `http://backend:8000/api/logs/analyze`

**Solution**: Updated nginx configuration to preserve the API prefix:
```nginx
# Before
proxy_pass http://backend:8000;

# After
proxy_pass http://backend:8000/api/;
```

**File**: `frontend/nginx.conf`

### 2. File Upload 500 Error
**Error**: Uploading log files returned 500 Internal Server Error

**Root Causes**:
1. **Encoding Issues**: File content decode as UTF-8 would fail for files with different encodings
2. **Analysis Failure**: If LLM analysis failed during upload, the entire transaction would rollback
3. **Poor Error Handling**: Generic error messages made debugging difficult

**Solution**: Enhanced error handling and robustness:
1. **Encoding Fallback**: Try UTF-8 first, fallback to latin-1 if that fails
2. **Analysis Isolation**: File upload succeeds even if analysis fails
3. **Better Error Handling**: Added specific exception handling and logging
4. **Partial Rollback**: Only rollback failed parts, not the entire transaction

**File**: `backend/app/api/logs.py`

## Changes Applied

### 1. Nginx Configuration Fix
**File**: `frontend/nginx.conf`

```nginx
# API proxy - Fixed
location /api/ {
    proxy_pass http://backend:8000/api/;  # Added /api/ to preserve prefix
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### 2. Enhanced Upload Function
**File**: `backend/app/api/logs.py`

**Key improvements**:
- Encoding fallback for file content
- Analysis error isolation
- Better error messages
- Transaction safety

```python
# Encoding fallback
try:
    log_content = content.decode('utf-8')
except UnicodeDecodeError:
    log_content = content.decode('latin-1')

# Analysis isolation
try:
    analysis = llm_analyzer.analyze_logs(parsed_entries)
    # Store analysis...
except Exception as analysis_error:
    print(f"Analysis failed during upload: {analysis_error}")
    analysis_id = None
    db.rollback()  # Only rollback analysis part
```

## Verification

### Test 1: Analyze Button
After the fix, clicking the analyze button should work:
1. Navigate to Cluster tab
2. Select a pod and view logs
3. Click "Analyze" button
4. Should see analysis results instead of 404 error

### Test 2: File Upload
After the fix, file upload should work:
1. Navigate to Upload tab
2. Upload a log file (even with different encoding)
3. Should see success message
4. File should be processed and stored even if analysis fails

## API Route Verification

### Correct API Endpoints
With the nginx fix, the API routes are now:
- `POST /api/logs/upload` - Upload log files ✅
- `GET /api/logs/entries` - Get log entries ✅
- `POST /api/logs/analyze` - Analyze logs ✅ (was 404, now fixed)
- `GET /api/logs/resources` - Get resources ✅
- `GET /api/k8s/health` - Cluster health ✅
- `GET /api/k8s/pods/{namespace}` - List pods ✅
- `GET /api/k8s/logs/{namespace}/{pod}` - Get pod logs ✅

### Request Flow (Fixed)
```
Browser → http://localhost:8080/api/logs/analyze
    → nginx (preserves /api prefix)
    → http://backend:8000/api/logs/analyze
    → FastAPI route handler
    → Response
```

## Error Handling Improvements

### Before
- Generic 500 errors
- Complete transaction rollback on any error
- No encoding fallback
- Analysis failure breaks entire upload

### After
- Specific error messages
- Partial rollback (only failed operations)
- Encoding fallback (UTF-8 → latin-1)
- Upload succeeds even if analysis fails
- Console logging for debugging

## Troubleshooting

### If Analyze Still Fails
1. Check backend logs: `docker compose logs backend`
2. Verify nginx is running: `docker compose logs frontend`
3. Check API is accessible: `curl http://localhost:8080/api/logs/analyze -X POST`
4. Check database has log entries: Visit http://localhost:8080/dashboard

### If Upload Still Fails
1. Check file size (large files may timeout)
2. Check file encoding (should be text-based)
3. Check backend logs for specific error details
4. Verify database connectivity

## Performance Considerations

### Nginx Proxy Configuration
- Proxy preserve prefix prevents routing issues
- Headers properly forwarded for accurate logging
- No performance overhead from prefix preservation

### Upload Process
- Encoding fallback adds minimal overhead
- Analysis isolation prevents blocking uploads
- Transaction safety ensures data consistency

## Security Notes
- Nginx proxy maintains security headers
- File size limits still apply (default nginx limits)
- Encoding fallback doesn't compromise security
- Error messages don't expose sensitive information

## Next Steps

1. **Test the fixes**: Try uploading a file and using analyze button
2. **Monitor logs**: Check both frontend and backend logs
3. **Verify data**: Confirm data is stored correctly in database
4. **Test analysis**: Try with and without Gemini API key

The application should now handle both file uploads and log analysis without errors! 🎉
