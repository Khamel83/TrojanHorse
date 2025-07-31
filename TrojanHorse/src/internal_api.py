#!/usr/bin/env python3
"""
Internal API Server for TrojanHorse Context Capture System
"""

from fastapi import FastAPI
import uvicorn
from search_engine import SearchEngine

app = FastAPI()
search_engine = SearchEngine()

@app.get("/search")
def search(query: str):
    results = search_engine.search(query, limit=3)
    return {"results": results}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5001)
