#!/bin/bash

echo "🚀 K8s Log Analytics - Quick Start Script"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from example..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your OPENAI_API_KEY"
    echo "   (Optional - app will work with basic analysis without it)"
    echo ""
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "🐳 Building and starting Docker containers..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

echo ""
echo "✅ Application started successfully!"
echo ""
echo "📊 Access the application at: http://localhost"
echo "📚 API Documentation at: http://localhost:8000/docs"
echo ""
echo "🔍 View logs with: docker-compose logs -f"
echo "🛑 Stop application with: docker-compose down"
echo ""
echo "📖 For more information, see README.md"
