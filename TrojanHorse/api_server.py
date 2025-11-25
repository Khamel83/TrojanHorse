"""FastAPI server for TrojanHorse - exposes core functionality via REST API."""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

from .config import Config
from .processor import Processor
from .rag import RAGIndex, rebuild_index, query
from .index_db import IndexDB
from .models import NoteMeta, parse_markdown_with_frontmatter

# Set up logging
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Initialize on startup
    try:
        app.state.config = Config.from_env()
        app.state.index_db = IndexDB(app.state.config.state_dir)
        app.state.rag_index = RAGIndex(app.state.config.state_dir, app.state.config)
        logger.info("TrojanHorse API initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize API: {e}")
        raise

    yield

    # Cleanup on shutdown
    try:
        if hasattr(app.state, 'rag_index'):
            app.state.rag_index.close()
        logger.info("TrojanHorse API shutdown complete")
    except Exception as e:
        logger.error(f"Error during API shutdown: {e}")


app = FastAPI(
    title="TrojanHorse API",
    description="REST API for TrojanHorse: Local Vault Processor + Q&A",
    version="0.1.0",
    lifespan=lifespan
)


# Request/Response Models
class AskRequest(BaseModel):
    question: str
    top_k: int = 8
    workspace: Optional[str] = None
    category: Optional[str] = None
    project: Optional[str] = None


class PromoteRequest(BaseModel):
    note_ids: List[str]


class ProcessResponse(BaseModel):
    files_scanned: int
    files_processed: int
    files_skipped: int
    duration_seconds: float
    errors: List[str] = []


class EmbedResponse(BaseModel):
    indexed_notes: int


class NoteMetadata(BaseModel):
    id: str
    source: str
    raw_type: str
    class_type: str
    category: str
    project: str
    created_at: datetime
    processed_at: datetime
    summary: str
    tags: List[str]
    original_path: str
    dest_path: str


class NoteResponse(BaseModel):
    meta: NoteMetadata
    content: Dict[str, Any]


class AskResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    contexts: List[Dict[str, Any]]


class PromoteResponse(BaseModel):
    items: List[Dict[str, Any]]


# Health Check
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "TrojanHorse API", "timestamp": datetime.now().isoformat()}


# Processing Endpoints
@app.post("/process", response_model=ProcessResponse)
async def process_once():
    """Trigger a single processing pass (equivalent to `th process`)."""
    try:
        config = app.state.config
        processor = Processor(config)
        stats = processor.process_once()

        return ProcessResponse(
            files_scanned=stats.files_scanned,
            files_processed=stats.files_processed,
            files_skipped=stats.files_skipped,
            duration_seconds=stats.duration_seconds,
            errors=stats.errors
        )
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed", response_model=EmbedResponse)
async def embed():
    """Rebuild/update embeddings index (equivalent to `th embed`)."""
    try:
        rebuild_index(app.state.config)

        # Get stats after rebuild
        rag_stats = app.state.rag_index.get_stats()
        return EmbedResponse(indexed_notes=rag_stats['total_notes'])
    except Exception as e:
        logger.error(f"Embedding rebuild failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Query Endpoints
@app.get("/notes")
async def list_notes(
    q: Optional[str] = None,
    workspace: Optional[str] = None,
    category: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List notes with optional filtering."""
    try:
        # Get all processed files from index database
        processed_files = app.state.index_db.get_all_files(limit=limit, offset=offset)

        notes = []
        for file_record in processed_files:
            # Try to parse the processed file to get metadata
            try:
                processed_path = Path(file_record['dest_path'])
                if processed_path.exists():
                    content = parse_markdown_with_frontmatter(processed_path)
                    if content and 'meta' in content:
                        meta = content['meta']

                        # Apply filters
                        if q and q.lower() not in str(meta).lower():
                            continue
                        if workspace and meta.get('workspace') != workspace:
                            continue
                        if category and meta.get('category') != category:
                            continue
                        if project and meta.get('project') != project:
                            continue

                        notes.append({
                            "id": meta.get('id', file_record['id']),
                            "source": meta.get('source', 'unknown'),
                            "raw_type": meta.get('raw_type', 'other'),
                            "class_type": meta.get('class_type', 'personal'),
                            "category": meta.get('category', 'other'),
                            "project": meta.get('project', 'none'),
                            "created_at": meta.get('created_at', datetime.now()),
                            "processed_at": meta.get('processed_at', datetime.now()),
                            "summary": meta.get('summary', ''),
                            "tags": meta.get('tags', []),
                            "original_path": file_record['original_path'],
                            "dest_path": file_record['dest_path']
                        })
            except Exception as e:
                logger.warning(f"Failed to parse processed file {file_record['dest_path']}: {e}")
                continue

        return {"items": notes, "total": len(notes)}

    except Exception as e:
        logger.error(f"Failed to list notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/notes/{note_id}", response_model=NoteResponse)
async def get_note(note_id: str):
    """Get a specific note by ID."""
    try:
        # First try to find in processed files
        file_record = app.state.index_db.get_file_by_id(note_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="Note not found")

        processed_path = Path(file_record['dest_path'])
        if not processed_path.exists():
            raise HTTPException(status_code=404, detail="Note file not found")

        content = parse_markdown_with_frontmatter(processed_path)
        if not content:
            raise HTTPException(status_code=404, detail="Could not parse note content")

        meta = content.get('meta', {})
        note_meta = NoteMetadata(
            id=meta.get('id', note_id),
            source=meta.get('source', 'unknown'),
            raw_type=meta.get('raw_type', 'other'),
            class_type=meta.get('class_type', 'personal'),
            category=meta.get('category', 'other'),
            project=meta.get('project', 'none'),
            created_at=meta.get('created_at', datetime.now()),
            processed_at=meta.get('processed_at', datetime.now()),
            summary=meta.get('summary', ''),
            tags=meta.get('tags', []),
            original_path=file_record['original_path'],
            dest_path=file_record['dest_path']
        )

        return NoteResponse(meta=note_meta, content=content)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get note {note_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask", response_model=AskResponse)
async def ask_question(req: AskRequest):
    """Ask a question and get answers from your notes."""
    try:
        # Query the RAG system
        result = query(
            app.state.config,
            req.question,
            k=req.top_k,
            workspace=req.workspace,
            category=req.category,
            project=req.project
        )

        return AskResponse(
            answer=result["answer"],
            sources=result.get("sources", []),
            contexts=result.get("contexts", [])
        )
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/promote", response_model=PromoteResponse)
async def promote_notes(req: PromoteRequest):
    """Prepare notes for export to Atlas."""
    try:
        notes = []

        for note_id in req.note_ids:
            # Get note metadata and content
            file_record = app.state.index_db.get_file_by_id(note_id)
            if not file_record:
                logger.warning(f"Note {note_id} not found, skipping")
                continue

            processed_path = Path(file_record['dest_path'])
            if not processed_path.exists():
                logger.warning(f"Note file {processed_path} not found, skipping")
                continue

            content = parse_markdown_with_frontmatter(processed_path)
            if not content:
                logger.warning(f"Could not parse note {note_id}, skipping")
                continue

            meta = content.get('meta', {})

            # Prepare note payload for Atlas
            note_payload = {
                "id": meta.get('id', note_id),
                "path": str(processed_path),
                "title": meta.get('title', processed_path.stem),
                "source": meta.get('source', 'unknown'),
                "raw_type": meta.get('raw_type', 'other'),
                "class_type": meta.get('class_type', 'personal'),
                "category": meta.get('category', 'other'),
                "project": meta.get('project', 'none'),
                "tags": meta.get('tags', []),
                "created_at": meta.get('created_at', datetime.now()).isoformat() if meta.get('created_at') else None,
                "updated_at": meta.get('updated_at', datetime.now()).isoformat() if meta.get('updated_at') else None,
                "summary": meta.get('summary', ''),
                "body": content.get('body', ''),
                "frontmatter": {k: v for k, v in meta.items() if k not in ['body', 'id']}
            }

            notes.append(note_payload)

        return PromoteResponse(items=notes)

    except Exception as e:
        logger.error(f"Failed to promote notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Stats Endpoint
@app.get("/stats")
async def get_stats():
    """Get system statistics."""
    try:
        # Processed files stats
        index_stats = app.state.index_db.get_stats()

        # RAG index stats
        rag_stats = app.state.rag_index.get_stats()

        return {
            "processed_files": {
                "total_files": index_stats['total_files'],
                "total_size_bytes": index_stats['total_size_bytes'],
                "total_size_mb": index_stats['total_size_bytes'] / (1024 * 1024)
            },
            "rag_index": {
                "total_notes": rag_stats['total_notes'],
                "categories": rag_stats.get('categories', {}),
                "projects": rag_stats.get('projects', {})
            },
            "config": {
                "vault_root": str(app.state.config.vault_root),
                "capture_dirs": [str(d) for d in app.state.config.capture_dirs],
                "llm_model": app.state.config.openrouter_model,
                "embedding_model": app.state.config.embedding_model_name
            }
        }

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))