"""
Knowledge Base API - Main FastAPI Application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.models import create_tables
from api.routes import router
from api.protected_routes import router as protected_router

# Create FastAPI app
app = FastAPI(
    title="Knowledge Base API",
    description="API for managing and searching educational knowledge base entries",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["knowledge-base"])
app.include_router(protected_router, prefix="/api/v1/protected", tags=["protected"])

@app.get("/")
def root():
    """Root endpoint"""
    return {"message": "Knowledge Base API", "version": "1.0.0"}

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.on_event("startup")
def startup_event():
    """Initialize database on startup"""
    create_tables()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

