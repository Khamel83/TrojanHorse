"""RAG (Retrieval-Augmented Generation) layer for querying notes."""

import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
import sqlite3

import numpy as np
import requests

from .config import Config
from .models import parse_markdown_with_frontmatter, NoteMeta
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Exception raised when embedding generation fails."""
    pass


class RAGIndex:
    """Vector index for RAG functionality."""

    def __init__(self, state_dir: Path, config: Config):
        """
        Initialize RAG index.

        Args:
            state_dir: Directory for storing index data
            config: Configuration object
        """
        self.state_dir = state_dir
        self.config = config
        self.db_path = state_dir / "rag_index.db"
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create the RAG index database."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Create embeddings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    note_id TEXT NOT NULL,
                    summary TEXT,
                    category TEXT,
                    project TEXT,
                    tags TEXT,
                    content_hash TEXT,
                    embedding BLOB,
                    created_at TEXT,
                    file_mtime REAL
                )
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_note_id ON embeddings(note_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON embeddings(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_project ON embeddings(project)")

            conn.commit()

        logger.debug(f"Initialized RAG index database: {self.db_path}")

    def _generate_embedding_api(self, text: str) -> List[float]:
        """
        Generate embedding using OpenAI API.

        Args:
            text: Text to embed

        Returns:
            List of embedding values

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not self.config.embedding_api_key:
            raise EmbeddingError("No embedding API key configured")

        headers = {
            "Authorization": f"Bearer {self.config.embedding_api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": self.config.embedding_model_name,
            "input": text,
        }

        try:
            response = requests.post(
                f"{self.config.embedding_api_base}/embeddings",
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()

            result = response.json()
            if "data" not in result or not result["data"]:
                raise EmbeddingError("Invalid embedding response format")

            return result["data"][0]["embedding"]

        except requests.RequestException as e:
            raise EmbeddingError(f"Embedding API request failed: {e}")
        except KeyError as e:
            raise EmbeddingError(f"Invalid embedding response: {e}")

    def _generate_embedding_simple(self, text: str) -> List[float]:
        """
        Generate a simple hash-based embedding (fallback).

        This is not a real embedding but provides deterministic vectors
        for basic functionality when no API is available.

        Args:
            text: Text to embed

        Returns:
            List of embedding values
        """
        # Create a deterministic but simple embedding based on text hash
        # This is NOT a semantic embedding, just a fallback
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()

        # Convert to float values in range [-1, 1]
        embedding = [(b / 255.0) * 2 - 1 for b in hash_bytes]

        # Standardize to 1536 dimensions (OpenAI default)
        target_dim = 1536
        if len(embedding) < target_dim:
            # Pad with repeated pattern
            pattern = embedding + embedding + embedding
            embedding = (pattern * ((target_dim // len(embedding)) + 1))[:target_dim]
        elif len(embedding) > target_dim:
            embedding = embedding[:target_dim]

        return embedding

    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            List of embedding values
        """
        try:
            # Try API-based embedding first
            if self.config.embedding_api_key:
                logger.debug("Using API-based embedding")
                return self._generate_embedding_api(text)
        except EmbeddingError as e:
            logger.warning(f"API embedding failed, using fallback: {e}")

        # Fallback to simple hash-based embedding
        logger.debug("Using fallback hash-based embedding")
        return self._generate_embedding_simple(text)

    def _text_to_embed(self, meta: NoteMeta, body: str) -> str:
        """
        Convert note to text for embedding.

        Args:
            meta: Note metadata
            body: Note body content

        Returns:
            Text to embed
        """
        # Combine summary with first part of body for embedding
        text_parts = []

        if meta.summary:
            text_parts.append(meta.summary)

        # Add first 2000 characters of body for context
        body_preview = body[:2000]
        if body_preview.strip():
            text_parts.append(body_preview)

        return " ".join(text_parts)

    def add_note(self, file_path: Path, meta: NoteMeta, body: str) -> None:
        """
        Add a note to the RAG index.

        Args:
            file_path: Path to the note file
            meta: Note metadata
            body: Note body content
        """
        try:
            # Generate content hash for change detection
            content_str = f"{meta.summary}_{body[:1000]}"  # Use summary and body preview
            content_hash = hashlib.sha256(content_str.encode()).hexdigest()

            # Check if already indexed and unchanged
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT content_hash FROM embeddings WHERE note_id = ?",
                    (meta.id,)
                )
                existing = cursor.fetchone()

                if existing and existing[0] == content_hash:
                    logger.debug(f"Note {meta.id} already indexed with same content")
                    return

            # Generate embedding
            text_to_embed = self._text_to_embed(meta, body)
            embedding = self._generate_embedding(text_to_embed)

            # Store in database
            embedding_bytes = json.dumps(embedding).encode()

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO embeddings
                    (id, file_path, note_id, summary, category, project, tags,
                     content_hash, embedding, created_at, file_mtime)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        hashlib.sha256(f"{meta.id}_{content_hash}".encode()).hexdigest(),
                        str(file_path.absolute()),
                        meta.id,
                        meta.summary,
                        meta.category,
                        meta.project,
                        json.dumps(meta.tags),
                        content_hash,
                        embedding_bytes,
                        meta.processed_at.isoformat(),
                        file_path.stat().st_mtime if file_path.exists() else 0
                    )
                )
                conn.commit()

            logger.debug(f"Added note to RAG index: {meta.id}")

        except Exception as e:
            logger.error(f"Failed to add note {meta.id} to RAG index: {e}")

    def search(self, query_text: str, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Search for similar notes.

        Args:
            query_text: Query text
            limit: Maximum number of results

        Returns:
            List of search results with similarity scores
        """
        try:
            # Generate embedding for query
            query_embedding = self._generate_embedding(query_text)
            query_np = np.array(query_embedding)

            # Get all embeddings from database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT note_id, file_path, summary, category, project, tags, embedding
                    FROM embeddings
                    ORDER BY created_at DESC
                """)
                rows = cursor.fetchall()

            if not rows:
                logger.debug("No embeddings found in RAG index")
                return []

            results = []
            for row in rows:
                try:
                    stored_embedding = json.loads(row[6])
                    stored_np = np.array(stored_embedding)

                    # Calculate cosine similarity
                    similarity = np.dot(query_np, stored_np) / (
                        np.linalg.norm(query_np) * np.linalg.norm(stored_np)
                    )

                    results.append({
                        "note_id": row[0],
                        "file_path": row[1],
                        "summary": row[2],
                        "category": row[3],
                        "project": row[4],
                        "tags": json.loads(row[5]),
                        "similarity": float(similarity)
                    })

                except Exception as e:
                    logger.warning(f"Error processing embedding for {row[0]}: {e}")
                    continue

            # Sort by similarity and return top results
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Error during RAG search: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """
        Get RAG index statistics.

        Returns:
            Dictionary with statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Total notes
                cursor.execute("SELECT COUNT(*) FROM embeddings")
                total_notes = cursor.fetchone()[0]

                # Category breakdown
                cursor.execute("""
                    SELECT category, COUNT(*)
                    FROM embeddings
                    WHERE category IS NOT NULL
                    GROUP BY category
                """)
                categories = dict(cursor.fetchall())

                return {
                    "total_notes": total_notes,
                    "categories": categories,
                    "db_path": str(self.db_path)
                }

        except Exception as e:
            logger.error(f"Error getting RAG stats: {e}")
            return {
                "total_notes": 0,
                "categories": {},
                "db_path": str(self.db_path)
            }

    def rebuild_index(self, config: Config) -> None:
        """
        Rebuild the entire RAG index from processed notes.

        Args:
            config: Configuration object
        """
        logger.info("Rebuilding RAG index...")

        try:
            # Clear existing index
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM embeddings")
                conn.commit()

            # Find processed notes directory
            if config.processed_root:
                base_dir = config.processed_root
            else:
                base_dir = config.vault_root

            # Find all markdown files in the processed directory
            md_files = list(base_dir.rglob("*.md"))
            logger.info(f"Found {len(md_files)} markdown files to index")

            indexed_count = 0
            for file_path in md_files:
                try:
                    # Parse the file
                    meta, body = parse_markdown_with_frontmatter(file_path)

                    if meta is None:
                        logger.debug(f"Skipping file without frontmatter: {file_path}")
                        continue

                    # Add to index
                    self.add_note(file_path, meta, body)
                    indexed_count += 1

                except Exception as e:
                    logger.warning(f"Error indexing {file_path}: {e}")
                    continue

            logger.info(f"RAG index rebuild complete: {indexed_count} notes indexed")

        except Exception as e:
            logger.error(f"Failed to rebuild RAG index: {e}")
            raise


def rebuild_index(config: Config) -> None:
    """
    Rebuild the RAG index.

    Args:
        config: Configuration object
    """
    rag_index = RAGIndex(config.state_dir, config)
    rag_index.rebuild_index(config)


def query(config: Config, question: str, k: int = 8) -> Dict[str, Any]:
    """
    Query the RAG index to answer a question.

    Args:
        config: Configuration object
        question: Question to answer
        k: Number of context notes to retrieve

    Returns:
        Dictionary with answer and context information
    """
    rag_index = RAGIndex(config.state_dir, config)

    # Search for relevant notes
    search_results = rag_index.search(question, limit=k)

    if not search_results:
        return {
            "answer": "I couldn't find any relevant notes to answer your question.",
            "contexts": []
        }

    # Build context from search results
    contexts = []
    context_text_parts = []

    for result in search_results:
        try:
            # Read the full content of the note
            file_path = Path(result["file_path"])
            if file_path.exists():
                _, body = parse_markdown_with_frontmatter(file_path)

                # Create context entry
                context_entry = {
                    "path": str(file_path),
                    "excerpt": body[:500] + "..." if len(body) > 500 else body,
                    "summary": result["summary"],
                    "similarity": result["similarity"]
                }
                contexts.append(context_entry)

                # Add to context text for LLM
                context_text_parts.append(
                    f"From {file_path.name} (similarity: {result['similarity']:.2f}):\n"
                    f"Summary: {result['summary']}\n"
                    f"Content: {body[:300]}...\n"
                )

        except Exception as e:
            logger.warning(f"Error reading note {result['file_path']}: {e}")
            continue

    if not contexts:
        return {
            "answer": "I found some potentially relevant notes but couldn't read their content.",
            "contexts": []
        }

    # Use LLM to answer question with context
    try:
        llm_client = LLMClient(config.openrouter_api_key, config.openrouter_model)

        context_text = "\n\n".join(context_text_parts)

        messages = [
            {
                "role": "system",
                "content": """You are an AI assistant that answers questions based on provided notes.
Use the context from the notes to provide accurate, helpful answers.
If the context doesn't contain enough information to fully answer the question, say so.
Be concise but thorough."""
            },
            {
                "role": "user",
                "content": f"""Question: {question}

Context from notes:
{context_text}

Please answer the question based on the provided context."""
            }
        ]

        answer = llm_client.call_chat(messages, temperature=0.3)

        return {
            "answer": answer,
            "contexts": contexts[:3]  # Return top 3 contexts for display
        }

    except Exception as e:
        logger.error(f"Error generating answer with LLM: {e}")
        return {
            "answer": f"I found some relevant notes but encountered an error generating an answer: {e}",
            "contexts": contexts[:3]
        }