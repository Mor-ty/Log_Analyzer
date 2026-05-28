@echo off
echo 🚀 K8s Log Analytics - Quick Start Script
echo ==========================================
echo.

REM Check if .env exists
if not exist .env (
    echo 📝 Creating .env file from example...
    copy .env.example .env
    echo ⚠️  Please edit .env and add your OPENAI_API_KEY
    echo    (Optional - app will work with basic analysis without it)
    echo.
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not running. Please start Docker Desktop and try again.
    pause
    exit /b 1
)

echo 🐳 Building and starting Docker containers...
docker-compose up -d

echo.
echo ⏳ Waiting for services to be ready...
timeout /t 10 /nobreak >nul

echo.
echo ✅ Application started successfully!
echo.
echo 📊 Access the application at: http://localhost
echo 📚 API Documentation at: http://localhost:8000/docs
echo.
echo 🔍 View logs with: docker-compose logs -f
echo 🛑 Stop application with: docker-compose down
echo.
echo 📖 For more information, see README.md
pause
