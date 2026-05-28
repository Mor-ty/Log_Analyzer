from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import init_db
from app.core.config import settings
from app.api import logs, kubernetes

# Initialize FastAPI app
app = FastAPI(
    title="K8s Log Analytics API",
    description="API for analyzing Kubernetes cluster logs using LLM",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(kubernetes.router, prefix="/api/k8s", tags=["kubernetes"])


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
    print("Database initialized")


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "K8s Log Analytics API",
        "version": "1.0.0",
        "endpoints": {
            "logs": "/api/logs",
            "kubernetes": "/api/k8s",
            "docs": "/docs"
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/debug/config")
def debug_config():
    """Debug endpoint to check configuration."""
    return {
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "gemini_key_length": len(settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else 0,
        "database_configured": bool(settings.DATABASE_URL),
        "redis_configured": bool(settings.REDIS_URL)
    }
