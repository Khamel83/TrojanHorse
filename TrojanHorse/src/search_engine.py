#!/usr/bin/env python3
"""
Search Engine Implementation for TrojanHorse Context Capture System
Phase 3: Search Engine Foundation - SQLite + FTS5 full-text search
"""

import sqlite3
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import re
from dataclasses import dataclass

@dataclass
class SearchResult:
    """Search result data structure"""
    transcript_id: int
    filename: str
    date: str
    timestamp: str
    content: str
    snippet: str
    score: float
    analysis_summary: Optional[str] = None
    action_items: Optional[List[str]] = None
    tags: Optional[List[str]] = None

class SearchEngine:
    """SQLite + FTS5 search engine for TrojanHorse transcripts"""
    
    def __init__(self, db_path: str = "trojan_search.db"):
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        self.conn = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize SQLite database with FTS5 schema"""
        try:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            
            # Load and execute schema
            schema_path = Path(__file__).parent / "database_schema.sql"
            if schema_path.exists():
                with open(schema_path, 'r') as f:
                    schema_sql = f.read()
                # Execute schema using executescript for multiple statements
                self.conn.executescript(schema_sql)
                self.logger.info("Database schema initialized successfully")
            else:
                self.logger.error(f"Schema file not found: {schema_path}")
                raise FileNotFoundError(f"Database schema file not found: {schema_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    def add_transcript(self, filename: str, date_str: str, timestamp_str: str, 
                      engine: str, file_path: str, content: str) -> int:
        """Add a transcript to the database"""
        try:
            word_count = len(content.split())
            
            cursor = self.conn.execute("""
                INSERT INTO transcripts (filename, date, timestamp, engine, file_path, content, word_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (filename, date_str, timestamp_str, engine, file_path, content, word_count))
            
            transcript_id = cursor.lastrowid
            self.conn.commit()
            
            self.logger.info(f"Added transcript: {filename} (ID: {transcript_id})")
            return transcript_id
            
        except sqlite3.IntegrityError:
            # Transcript already exists
            cursor = self.conn.execute("SELECT id FROM transcripts WHERE filename = ?", (filename,))
            result = cursor.fetchone()
            if result:
                return result['id']
            raise
        except Exception as e:
            self.logger.error(f"Failed to add transcript {filename}: {e}")
            raise
    
    def add_analysis(self, transcript_id: int, mode: str, model: str, 
                    summary: str, action_items: List[str], tags: List[str],
                    classification: str, sentiment: str, confidence: float,
                    file_path: str) -> int:
        """Add analysis results to the database"""
        try:
            cursor = self.conn.execute("""
                INSERT INTO analysis (transcript_id, mode, model, summary, action_items, 
                                    tags, classification, sentiment, confidence, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (transcript_id, mode, model, summary, 
                  json.dumps(action_items), json.dumps(tags),
                  classification, sentiment, confidence, file_path))
            
            analysis_id = cursor.lastrowid
            self.conn.commit()
            
            self.logger.info(f"Added analysis for transcript {transcript_id} (ID: {analysis_id})")
            return analysis_id
            
        except Exception as e:
            self.logger.error(f"Failed to add analysis for transcript {transcript_id}: {e}")
            raise
    
    def search(self, query: str, limit: int = 50, offset: int = 0,
              date_from: Optional[str] = None, date_to: Optional[str] = None,
              classification: Optional[str] = None) -> List[SearchResult]:
        """
        Perform full-text search on transcripts and analysis
        
        Args:
            query: Search query string
            limit: Maximum number of results
            offset: Results offset for pagination
            date_from: Start date filter (YYYY-MM-DD)
            date_to: End date filter (YYYY-MM-DD)
            classification: Filter by content classification
        """
        try:
            # Prepare FTS5 query (escape special characters)
            fts_query = self._prepare_fts_query(query)
            
            # Build search SQL with filters
            search_sql, params = self._build_search_query(
                fts_query, limit, offset, date_from, date_to, classification
            )
            
            cursor = self.conn.execute(search_sql, params)
            results = []
            
            for row in cursor.fetchall():
                snippet = self._generate_snippet(row['content'], query)
                
                # Parse JSON fields
                action_items = json.loads(row['action_items']) if row['action_items'] else None
                tags = json.loads(row['tags']) if row['tags'] else None
                
                result = SearchResult(
                    transcript_id=row['transcript_id'],
                    filename=row['filename'],
                    date=row['date'],
                    timestamp=row['timestamp'],
                    content=row['content'],
                    snippet=snippet,
                    score=row['rank'],
                    analysis_summary=row['summary'],
                    action_items=action_items,
                    tags=tags
                )
                results.append(result)
            
            self.logger.info(f"Search '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            self.logger.error(f"Search failed for query '{query}': {e}")
            raise
    
    def _prepare_fts_query(self, query: str) -> str:
        """Prepare query for FTS5 (escape special characters, handle phrases)"""
        # Remove special FTS5 characters that might cause issues
        query = re.sub(r'[^\w\s\-\.]', ' ', query)
        
        # Split into terms and join with OR for broader matching
        terms = [term.strip() for term in query.split() if term.strip()]
        
        if len(terms) == 1:
            return f'"{terms[0]}"*'  # Prefix matching for single terms
        else:
            # For multi-term queries, try exact phrase first, then individual terms
            phrase_query = f'"{" ".join(terms)}"'
            term_queries = [f'"{term}"*' for term in terms]
            return f'({phrase_query}) OR ({" OR ".join(term_queries)})'
    
    def _build_search_query(self, fts_query: str, limit: int, offset: int,
                           date_from: Optional[str], date_to: Optional[str],
                           classification: Optional[str]) -> Tuple[str, List]:
        """Build search SQL query with filters"""
        
        search_sql = """
        SELECT DISTINCT
            t.id as transcript_id,
            t.filename,
            t.date,
            t.timestamp,
            t.content,
            a.summary,
            a.action_items,
            a.tags,
            a.classification,
            (COALESCE(t_rank.rank, 0) + COALESCE(a_rank.rank, 0)) as rank
        FROM transcripts t
        LEFT JOIN analysis a ON t.id = a.transcript_id
        LEFT JOIN (
            SELECT rowid, rank FROM transcripts_fts WHERE transcripts_fts MATCH ?
        ) t_rank ON t.id = t_rank.rowid
        LEFT JOIN (
            SELECT rowid, rank FROM analysis_fts WHERE analysis_fts MATCH ?
        ) a_rank ON a.id = a_rank.rowid
        WHERE (t_rank.rank IS NOT NULL OR a_rank.rank IS NOT NULL)
        """
        
        params = [fts_query, fts_query]
        
        # Add date filters
        if date_from:
            search_sql += " AND t.date >= ?"
            params.append(date_from)
        
        if date_to:
            search_sql += " AND t.date <= ?"
            params.append(date_to)
        
        # Add classification filter
        if classification:
            search_sql += " AND a.classification = ?"
            params.append(classification)
        
        # Order by relevance and recency
        search_sql += """
        ORDER BY rank DESC, t.timestamp DESC
        LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        
        return search_sql, params
    
    def _generate_snippet(self, content: str, query: str, snippet_length: int = 200) -> str:
        """Generate a snippet around search terms"""
        query_terms = query.lower().split()
        content_lower = content.lower()
        
        # Find the first occurrence of any query term
        best_pos = len(content)
        for term in query_terms:
            pos = content_lower.find(term.lower())
            if pos != -1 and pos < best_pos:
                best_pos = pos
        
        if best_pos == len(content):
            # No terms found, return beginning
            return content[:snippet_length] + ("..." if len(content) > snippet_length else "")
        
        # Center the snippet around the found term
        start = max(0, best_pos - snippet_length // 2)
        end = min(len(content), start + snippet_length)
        
        # Adjust start if we're at the end
        if end == len(content) and len(content) > snippet_length:
            start = max(0, end - snippet_length)
        
        snippet = content[start:end]
        
        # Add ellipsis if needed
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            cursor = self.conn.execute("""
                SELECT 
                    COUNT(*) as total_transcripts,
                    MIN(date) as earliest_date,
                    MAX(date) as latest_date,
                    SUM(word_count) as total_words
                FROM transcripts
            """)
            transcript_stats = cursor.fetchone()
            
            cursor = self.conn.execute("SELECT COUNT(*) as total_analysis FROM analysis")
            analysis_stats = cursor.fetchone()
            
            cursor = self.conn.execute("""
                SELECT classification, COUNT(*) as count 
                FROM analysis 
                WHERE classification IS NOT NULL 
                GROUP BY classification
            """)
            classifications = dict(cursor.fetchall())
            
            return {
                'total_transcripts': transcript_stats['total_transcripts'],
                'total_analysis': analysis_stats['total_analysis'],
                'earliest_date': transcript_stats['earliest_date'],
                'latest_date': transcript_stats['latest_date'],
                'total_words': transcript_stats['total_words'],
                'classifications': classifications
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get stats: {e}")
            return {}
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed")

def main():
    """Test the search engine"""
    logging.basicConfig(level=logging.INFO)
    
    # Initialize search engine
    search = SearchEngine("test_search.db")
    
    try:
        # Test adding a transcript
        transcript_id = search.add_transcript(
            filename="test_audio_123456.txt",
            date_str="2025-07-31",
            timestamp_str="2025-07-31T14:30:00",
            engine="macwhisper",
            file_path="/path/to/transcript.txt",
            content="This is a test transcript for the search engine. We're discussing project planning and task management."
        )
        
        # Test adding analysis
        search.add_analysis(
            transcript_id=transcript_id,
            mode="local",
            model="deepseek-r1:8b",
            summary="Discussion about project planning and task management",
            action_items=["Set up search engine", "Test functionality"],
            tags=["project", "planning", "tasks"],
            classification="meeting",
            sentiment="positive",
            confidence=0.85,
            file_path="/path/to/analysis.md"
        )
        
        # Test search
        results = search.search("project planning")
        print(f"Found {len(results)} results")
        for result in results:
            print(f"- {result.filename}: {result.snippet}")
        
        # Test stats
        stats = search.get_stats()
        print(f"Database stats: {stats}")
        
    finally:
        search.close()

if __name__ == "__main__":
    main()