#!/usr/bin/env python3
"""
Internal API Server for TrojanHorse Context Capture System
"""

from fastapi import FastAPI, HTTPException
from config_manager import ConfigManager
import uvicorn
import logging
from datetime import datetime
from search_engine import SearchEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TrojanHorse Internal API", version="1.0.0")

# Initialize search engine
try:
    search_engine = SearchEngine()
    logger.info("Search engine initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize search engine: {e}")
    search_engine = None

@app.get("/search")
def search(query: str):
    """Search transcripts and return top 3 results"""
    if not search_engine:
        raise HTTPException(status_code=500, detail="Search engine not available")
    
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query parameter is required")
    
    try:
        results = search_engine.search(query.strip(), limit=3)
        return {"query": query, "results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

@app.get("/health")
def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "search_available": search_engine is not None,
        "timestamp": str(datetime.now())
    }

if __name__ == "__main__":
    # Load configuration for port
    config_manager = ConfigManager()
    port = config_manager.get_value("workflow_integration.internal_api_port") or 5001
    
    logger.info(f"Starting internal API server on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
