#!/usr/bin/env python3
"""
Semantic Search Implementation for TrojanHorse Context Capture System
Phase 3: Semantic Search - Vector embeddings for conceptual similarity search
"""

import sqlite3
import json
import logging
import pickle
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

@dataclass
class SemanticResult:
    """Semantic search result data structure"""
    transcript_id: int
    filename: str
    date: str
    timestamp: str
    content: str
    snippet: str
    similarity: float
    chunk_index: int = 0
    analysis_summary: Optional[str] = None
    action_items: Optional[List[str]] = None
    tags: Optional[List[str]] = None

class SemanticSearch:
    """Vector embedding-based semantic search for TrojanHorse transcripts"""
    
    def __init__(self, db_path: str = "trojan_search.db", 
                 model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize semantic search with sentence transformer model
        
        Args:
            db_path: SQLite database path
            model_name: HuggingFace model for embeddings
                       - all-MiniLM-L6-v2: Fast, good quality (384 dim)
                       - all-mpnet-base-v2: Higher quality (768 dim)
                       - paraphrase-MiniLM-L12-v2: Good for paraphrases
        """
        self.db_path = Path(db_path)
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)
        self.conn = None
        self.model = None
        
        # Configuration
        self.chunk_size = 500  # Characters per chunk for long transcripts
        self.chunk_overlap = 50  # Character overlap between chunks
        
        self._initialize_database()
        self._load_model()
    
    def _initialize_database(self):
        """Initialize database connection"""
        try:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.logger.info("Connected to semantic search database")
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")
            raise
    
    def _load_model(self):
        """Load sentence transformer model"""
        try:
            self.logger.info(f"Loading sentence transformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            self.logger.info(f"Model loaded successfully, embedding dimension: {self.embedding_dim}")
        except Exception as e:
            self.logger.error(f"Failed to load sentence transformer model: {e}")
            raise
    
    def generate_embeddings(self, transcript_id: int, content: str) -> List[Tuple[int, np.ndarray]]:
        """
        Generate embeddings for transcript content, chunking if necessary
        
        Returns:
            List of (chunk_index, embedding) tuples
        """
        try:
            # Split long content into chunks
            chunks = self._chunk_content(content)
            embeddings = []
            
            for chunk_index, chunk_text in enumerate(chunks):
                if len(chunk_text.strip()) < 10:  # Skip very short chunks
                    continue
                
                # Generate embedding
                embedding = self.model.encode(chunk_text, convert_to_numpy=True)
                
                # Store in database
                self._store_embedding(transcript_id, chunk_index, chunk_text, embedding)
                
                embeddings.append((chunk_index, embedding))
                
                self.logger.debug(f"Generated embedding for transcript {transcript_id}, chunk {chunk_index}")
            
            self.logger.info(f"Generated {len(embeddings)} embeddings for transcript {transcript_id}")
            return embeddings
            
        except Exception as e:
            self.logger.error(f"Failed to generate embeddings for transcript {transcript_id}: {e}")
            raise
    
    def _chunk_content(self, content: str) -> List[str]:
        """Split content into overlapping chunks for better context"""
        if len(content) <= self.chunk_size:
            return [content]
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + self.chunk_size
            
            # If this isn't the last chunk, try to break at a sentence boundary
            if end < len(content):
                # Look for sentence endings within the last 100 characters
                last_sentence = max(
                    content.rfind('.', start, end),
                    content.rfind('!', start, end),
                    content.rfind('?', start, end)
                )
                
                if last_sentence > start + self.chunk_size // 2:
                    end = last_sentence + 1
            
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = end - self.chunk_overlap
            
            if start >= len(content):
                break
        
        return chunks
    
    def _store_embedding(self, transcript_id: int, chunk_index: int, 
                        chunk_text: str, embedding: np.ndarray):
        """Store embedding in database"""
        try:
            # Serialize embedding as bytes
            embedding_bytes = pickle.dumps(embedding)
            
            # Insert or replace embedding
            self.conn.execute("""
                INSERT OR REPLACE INTO embeddings 
                (transcript_id, chunk_index, chunk_text, embedding)
                VALUES (?, ?, ?, ?)
            """, (transcript_id, chunk_index, chunk_text, embedding_bytes))
            
            self.conn.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to store embedding: {e}")
            raise
    
    def semantic_search(self, query: str, limit: int = 20, 
                       similarity_threshold: float = 0.3,
                       date_from: Optional[str] = None, 
                       date_to: Optional[str] = None) -> List[SemanticResult]:
        """
        Perform semantic similarity search
        
        Args:
            query: Search query string
            limit: Maximum number of results
            similarity_threshold: Minimum cosine similarity (0-1)
            date_from: Start date filter (YYYY-MM-DD)
            date_to: End date filter (YYYY-MM-DD)
        """
        try:
            # Generate query embedding
            query_embedding = self.model.encode(query, convert_to_numpy=True)
            
            # Get all embeddings from database with filters
            embeddings_sql = """
                SELECT e.transcript_id, e.chunk_index, e.chunk_text, e.embedding,
                       t.filename, t.date, t.timestamp, t.content,
                       a.summary, a.action_items, a.tags
                FROM embeddings e
                JOIN transcripts t ON e.transcript_id = t.id
                LEFT JOIN analysis a ON t.id = a.transcript_id
            """
            
            params = []
            
            # Add date filters
            if date_from or date_to:
                embeddings_sql += " WHERE "
                conditions = []
                
                if date_from:
                    conditions.append("t.date >= ?")
                    params.append(date_from)
                
                if date_to:
                    conditions.append("t.date <= ?")
                    params.append(date_to)
                
                embeddings_sql += " AND ".join(conditions)
            
            cursor = self.conn.execute(embeddings_sql, params)
            results = []
            
            for row in cursor.fetchall():
                try:
                    # Deserialize embedding
                    stored_embedding = pickle.loads(row['embedding'])
                    
                    # Calculate cosine similarity
                    similarity = cosine_similarity(
                        query_embedding.reshape(1, -1),
                        stored_embedding.reshape(1, -1)
                    )[0][0]
                    
                    # Filter by threshold
                    if similarity < similarity_threshold:
                        continue
                    
                    # Parse JSON fields
                    action_items = json.loads(row['action_items']) if row['action_items'] else None
                    tags = json.loads(row['tags']) if row['tags'] else None
                    
                    # Create result
                    result = SemanticResult(
                        transcript_id=row['transcript_id'],
                        filename=row['filename'],
                        date=row['date'],
                        timestamp=row['timestamp'],
                        content=row['content'],
                        snippet=row['chunk_text'],
                        similarity=float(similarity),
                        chunk_index=row['chunk_index'],
                        analysis_summary=row['summary'],
                        action_items=action_items,
                        tags=tags
                    )
                    
                    results.append(result)
                    
                except Exception as e:
                    self.logger.warning(f"Error processing embedding result: {e}")
                    continue
            
            # Sort by similarity (highest first) and limit results
            results.sort(key=lambda x: x.similarity, reverse=True)
            results = results[:limit]
            
            self.logger.info(f"Semantic search '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            self.logger.error(f"Semantic search failed for query '{query}': {e}")
            raise
    
    def hybrid_search(self, query: str, limit: int = 20,
                     keyword_weight: float = 0.7, semantic_weight: float = 0.3,
                     date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Combine keyword and semantic search with weighted scoring
        
        Args:
            query: Search query string
            limit: Maximum number of results
            keyword_weight: Weight for keyword search scores (0-1)
            semantic_weight: Weight for semantic search scores (0-1)
            date_from: Start date filter (YYYY-MM-DD)
            date_to: End date filter (YYYY-MM-DD)
        """
        try:
            # Import SearchEngine here to avoid circular imports
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).parent))
            from search_engine import SearchEngine
            
            # Get keyword search results
            keyword_search = SearchEngine(str(self.db_path))
            keyword_results = keyword_search.search(
                query, limit=limit*2, date_from=date_from, date_to=date_to
            )
            
            # Get semantic search results
            semantic_results = self.semantic_search(
                query, limit=limit*2, date_from=date_from, date_to=date_to
            )
            
            # Combine and score results
            combined_results = {}
            
            # Add keyword results
            max_keyword_score = max([r.score for r in keyword_results]) if keyword_results else 1.0
            for result in keyword_results:
                transcript_id = result.transcript_id
                normalized_score = result.score / max_keyword_score
                
                combined_results[transcript_id] = {
                    'transcript_id': transcript_id,
                    'filename': result.filename,
                    'date': result.date,
                    'timestamp': result.timestamp,
                    'content': result.content,
                    'snippet': result.snippet,
                    'keyword_score': normalized_score,
                    'semantic_score': 0.0,
                    'combined_score': normalized_score * keyword_weight,
                    'analysis_summary': result.analysis_summary,
                    'action_items': result.action_items,
                    'tags': result.tags,
                    'source': 'keyword'
                }
            
            # Add semantic results (and merge if transcript already exists)
            max_semantic_score = max([r.similarity for r in semantic_results]) if semantic_results else 1.0
            for result in semantic_results:
                transcript_id = result.transcript_id
                normalized_score = result.similarity / max_semantic_score
                
                if transcript_id in combined_results:
                    # Update existing result
                    combined_results[transcript_id]['semantic_score'] = normalized_score
                    combined_results[transcript_id]['combined_score'] = (
                        combined_results[transcript_id]['keyword_score'] * keyword_weight +
                        normalized_score * semantic_weight
                    )
                    combined_results[transcript_id]['source'] = 'hybrid'
                    
                    # Use semantic snippet if it has higher similarity
                    if normalized_score > combined_results[transcript_id]['keyword_score']:
                        combined_results[transcript_id]['snippet'] = result.snippet
                else:
                    # Add new semantic-only result
                    combined_results[transcript_id] = {
                        'transcript_id': transcript_id,
                        'filename': result.filename,
                        'date': result.date,
                        'timestamp': result.timestamp,
                        'content': result.content,
                        'snippet': result.snippet,
                        'keyword_score': 0.0,
                        'semantic_score': normalized_score,
                        'combined_score': normalized_score * semantic_weight,
                        'analysis_summary': result.analysis_summary,
                        'action_items': result.action_items,
                        'tags': result.tags,
                        'source': 'semantic'
                    }
            
            # Sort by combined score and limit
            final_results = list(combined_results.values())
            final_results.sort(key=lambda x: x['combined_score'], reverse=True)
            final_results = final_results[:limit]
            
            keyword_search.close()
            
            self.logger.info(f"Hybrid search '{query}' returned {len(final_results)} results")
            return final_results
            
        except Exception as e:
            self.logger.error(f"Hybrid search failed for query '{query}': {e}")
            raise
    
    def batch_generate_embeddings(self, force_regenerate: bool = False) -> Dict[str, int]:
        """
        Generate embeddings for all transcripts that don't have them
        
        Args:
            force_regenerate: Regenerate embeddings even if they exist
        """
        try:
            # Get transcripts that need embeddings
            if force_regenerate:
                sql = "SELECT id, content FROM transcripts"
                params = []
            else:
                sql = """
                    SELECT t.id, t.content 
                    FROM transcripts t 
                    LEFT JOIN embeddings e ON t.id = e.transcript_id 
                    WHERE e.transcript_id IS NULL
                """
                params = []
            
            cursor = self.conn.execute(sql, params)
            transcripts = cursor.fetchall()
            
            stats = {
                'processed': 0,
                'embeddings_generated': 0,
                'errors': 0
            }
            
            self.logger.info(f"Generating embeddings for {len(transcripts)} transcripts")
            
            for row in transcripts:
                try:
                    if force_regenerate:
                        # Delete existing embeddings
                        self.conn.execute(
                            "DELETE FROM embeddings WHERE transcript_id = ?", 
                            (row['id'],)
                        )
                        self.conn.commit()
                    
                    # Generate new embeddings
                    embeddings = self.generate_embeddings(row['id'], row['content'])
                    
                    stats['processed'] += 1
                    stats['embeddings_generated'] += len(embeddings)
                    
                    if stats['processed'] % 10 == 0:
                        self.logger.info(f"Processed {stats['processed']}/{len(transcripts)} transcripts")
                    
                except Exception as e:
                    self.logger.error(f"Error generating embeddings for transcript {row['id']}: {e}")
                    stats['errors'] += 1
            
            self.logger.info(f"Batch embedding generation complete: {stats}")
            return stats
            
        except Exception as e:
            self.logger.error(f"Batch embedding generation failed: {e}")
            raise
    
    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get statistics about stored embeddings"""
        try:
            cursor = self.conn.execute("""
                SELECT 
                    COUNT(DISTINCT transcript_id) as transcripts_with_embeddings,
                    COUNT(*) as total_embeddings,
                    AVG(LENGTH(chunk_text)) as avg_chunk_length
                FROM embeddings
            """)
            stats = dict(cursor.fetchone())
            
            cursor = self.conn.execute("SELECT COUNT(*) as total_transcripts FROM transcripts")
            total_transcripts = cursor.fetchone()['total_transcripts']
            
            stats['total_transcripts'] = total_transcripts
            stats['coverage_percent'] = (
                stats['transcripts_with_embeddings'] / total_transcripts * 100 
                if total_transcripts > 0 else 0
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get embedding stats: {e}")
            return {}
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.logger.info("Semantic search database connection closed")

def main():
    """Test semantic search functionality"""
    logging.basicConfig(level=logging.INFO)
    
    # Initialize semantic search
    semantic = SemanticSearch("test_semantic.db")
    
    try:
        # Generate embeddings for existing transcripts
        print("=== Generating Embeddings ===")
        stats = semantic.batch_generate_embeddings()
        print(f"Embedding generation stats: {stats}")
        
        # Test semantic search
        print("\n=== Testing Semantic Search ===")
        
        test_queries = [
            "project planning and management",
            "technical implementation details",
            "meeting discussions and decisions",
            "task coordination and workflow"
        ]
        
        for query in test_queries:
            print(f"\n--- Semantic Search: '{query}' ---")
            results = semantic.semantic_search(query, limit=3)
            print(f"Found {len(results)} results")
            
            for i, result in enumerate(results, 1):
                print(f"{i}. {result.filename} (similarity: {result.similarity:.3f})")
                print(f"   Snippet: {result.snippet[:200]}...")
                print()
        
        # Test hybrid search
        print("\n=== Testing Hybrid Search ===")
        results = semantic.hybrid_search("project planning", limit=3)
        print(f"Found {len(results)} hybrid results")
        
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['filename']} (score: {result['combined_score']:.3f})")
            print(f"   Source: {result['source']}")
            print(f"   Snippet: {result['snippet'][:200]}...")
            print()
        
        # Get embedding stats
        stats = semantic.get_embedding_stats()
        print(f"\nEmbedding stats: {stats}")
        
    finally:
        semantic.close()

if __name__ == "__main__":
    main()