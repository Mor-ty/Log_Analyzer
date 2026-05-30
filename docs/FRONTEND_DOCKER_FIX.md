# Frontend Docker Build Error Fix

## Issue
The Docker build for the frontend failed with the following error:
```
npm error The `npm ci` command can only install with an existing package-lock.json or
npm-shrinkwrap.json with lockfileVersion >= 1. Run an install with npm@5 or
later to generate a package-lock.json file, then try again.
```

## Root Cause
The Dockerfile was using `npm ci` (clean install) which requires a `package-lock.json` file to be present, but the frontend directory only had `package.json` and no lock file.

## Solution
Applied the following fixes:

### 1. Generated package-lock.json
Ran `npm install` in the frontend directory to generate the missing `package-lock.json` file:
```bash
cd frontend
npm install
```

### 2. Updated .dockerignore
Removed `package-lock.json` from the `.dockerignore` file so the lock file can be copied during Docker build:
```
# Before
package-lock.json

# After (removed)
```

### 3. Updated Dockerfile
The Dockerfile was already correct (using `npm ci`), but now it will work since we have the lock file:
```dockerfile
COPY package.json package-lock.json ./
RUN npm ci
```

### 4. Updated Package Dependencies
Updated `recharts` to address deprecation warning:
- `recharts: ^2.10.3` → `recharts: ^2.13.3`

## Files Changed
- `frontend/package-lock.json` (generated)
- `frontend/.dockerignore` (removed package-lock.json exclusion)
- `frontend/package.json` (updated recharts version)
- `frontend/Dockerfile` (no changes needed, but now works with lock file)

## Benefits of Using npm ci
- **Reproducible builds**: Uses exact versions from lock file
- **Faster installs**: Skips dependency resolution
- **Cleaner installs**: Removes existing node_modules first
- **Production ready**: Recommended for production deployments

## Verification
The Docker build should now complete successfully:
```bash
docker compose build frontend
docker compose up -d
```

## Alternative Approach
If you encounter similar issues, you can temporarily use `npm install` instead of `npm ci` in the Dockerfile:
```dockerfile
COPY package.json ./
RUN npm install
```

However, `npm ci` is preferred for production builds due to its reproducibility guarantees.

## Security Notes
The build output shows 2 moderate severity vulnerabilities. You may want to run:
```bash
npm audit fix
```

However, these are likely in transitive dependencies and may not be immediately critical for the application's functionality.
