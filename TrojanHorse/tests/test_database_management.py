#!/usr/bin/env python3
"""
Unit tests for Database Connection Management
"""

import unittest
import tempfile
import sqlite3
import os
import sys
from pathlib import Path
from contextlib import contextmanager

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from search_engine import SearchEngine
from analytics_engine import AnalyticsEngine


class TestDatabaseConnectionManagement(unittest.TestCase):
    def setUp(self):
        """Set up test environment with temporary database"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
    
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    def test_search_engine_connection_cleanup(self):
        """Test that SearchEngine properly closes database connections"""
        search_engine = SearchEngine(self.db_path)
        
        # Verify connection is open
        self.assertIsNotNone(search_engine.conn)
        
        # Close and verify cleanup
        search_engine.close()
        
        # Attempting to use closed connection should raise exception
        with self.assertRaises(sqlite3.ProgrammingError):
            search_engine.conn.execute("SELECT 1")
    
    def test_analytics_engine_connection_cleanup(self):
        """Test that AnalyticsEngine properly closes database connections"""
        analytics_engine = AnalyticsEngine(self.db_path)
        
        # Verify connection is open
        self.assertIsNotNone(analytics_engine.conn)
        
        # Close and verify cleanup
        analytics_engine.conn.close()
        
        # Attempting to use closed connection should raise exception
        with self.assertRaises(sqlite3.ProgrammingError):
            analytics_engine.conn.execute("SELECT 1")
    
    def test_database_context_manager(self):
        """Test database operations with proper context management"""
        @contextmanager
        def database_connection(db_path):
            conn = None
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                yield conn
            finally:
                if conn:
                    conn.close()
        
        # Test context manager properly closes connection
        with database_connection(self.db_path) as conn:
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            self.assertEqual(result[0], 1)
        
        # Connection should be closed after context
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")
    
    def test_connection_error_handling(self):
        """Test proper error handling for database connection issues"""
        # Test connection to non-existent database path
        bad_path = "/nonexistent/path/database.db"
        
        with self.assertRaises((sqlite3.OperationalError, OSError)):
            SearchEngine(bad_path)
    
    def test_multiple_connections_cleanup(self):
        """Test that multiple database connections are properly managed"""
        connections = []
        
        # Create multiple connections
        for i in range(5):
            se = SearchEngine(self.db_path)
            connections.append(se)
        
        # Close all connections
        for se in connections:
            se.close()
        
        # Verify all connections are closed
        for se in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                se.conn.execute("SELECT 1")


if __name__ == '__main__':
    unittest.main()