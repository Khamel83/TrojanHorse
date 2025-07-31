#!/usr/bin/env python3
"""
Unit tests for SearchEngine
"""

import unittest
import tempfile
import sqlite3
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from search_engine import SearchEngine


class TestSearchEngine(unittest.TestCase):
    def setUp(self):
        """Set up test environment with temporary database"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Initialize search engine with test database
        self.search_engine = SearchEngine(self.db_path)
        
        # Add test data
        self._add_test_data()
    
    def tearDown(self):
        """Clean up test environment"""
        self.search_engine.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    def _add_test_data(self):
        """Add test transcripts to database"""
        test_transcripts = [
            {
                'filename': 'test1.txt',
                'date': '2025-01-01',
                'timestamp': '2025-01-01T10:00:00',
                'engine': 'test',
                'file_path': '/test/path1.txt',
                'content': 'This is a test transcript about artificial intelligence and machine learning.',
                'word_count': 12
            },
            {
                'filename': 'test2.txt', 
                'date': '2025-01-02',
                'timestamp': '2025-01-02T10:00:00',
                'engine': 'test',
                'file_path': '/test/path2.txt',
                'content': 'Another test document discussing natural language processing and AI systems.',
                'word_count': 11
            }
        ]
        
        for transcript in test_transcripts:
            self.search_engine.conn.execute("""
                INSERT INTO transcripts (filename, date, timestamp, engine, file_path, content, word_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                transcript['filename'], transcript['date'], transcript['timestamp'],
                transcript['engine'], transcript['file_path'], transcript['content'], transcript['word_count']
            ))
        
        self.search_engine.conn.commit()
    
    def test_search_functionality(self):
        """Test basic search functionality"""
        # Test keyword search
        results = self.search_engine.search("artificial intelligence")
        self.assertGreater(len(results), 0)
        self.assertIn("artificial intelligence", results[0].content.lower())
        
        # Test search with no results
        results = self.search_engine.search("nonexistent term")
        self.assertEqual(len(results), 0)
    
    def test_get_stats(self):
        """Test database statistics"""
        stats = self.search_engine.get_stats()
        self.assertIn('total_transcripts', stats)
        self.assertIn('total_words', stats)
        self.assertEqual(stats['total_transcripts'], 2)
        self.assertEqual(stats['total_words'], 23)
    
    def test_search_with_limit(self):
        """Test search with result limit"""
        results = self.search_engine.search("test", limit=1)
        self.assertLessEqual(len(results), 1)
    
    def test_database_connection(self):
        """Test database connection is working"""
        self.assertIsNotNone(self.search_engine.conn)
        
        # Test can execute queries
        cursor = self.search_engine.conn.execute("SELECT COUNT(*) FROM transcripts")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 2)


if __name__ == '__main__':
    unittest.main()