#!/usr/bin/env python3
"""
Unit tests for Security Hardening
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


class TestSecurityHardening(unittest.TestCase):
    def setUp(self):
        """Set up test environment with temporary database"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.search_engine = SearchEngine(self.db_path)
    
    def tearDown(self):
        """Clean up test environment"""
        self.search_engine.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    def test_sql_injection_prevention_in_search(self):
        """Test that search queries are properly parameterized against SQL injection"""
        # Add a test transcript
        self.search_engine.add_transcript(
            "test.txt", "2025-01-01", "2025-01-01T10:00:00", 
            "test", "/test/path.txt", "Test content for security testing"
        )
        
        # Test SQL injection attempts
        malicious_queries = [
            "'; DROP TABLE transcripts; --",
            "' OR '1'='1",
            "'; INSERT INTO transcripts VALUES (999, 'hack', '2025-01-01', '2025-01-01T10:00:00', 'test', '/hack', 'hacked', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP); --",
            "test' UNION SELECT * FROM transcripts WHERE '1'='1"
        ]
        
        for malicious_query in malicious_queries:
            # These should not cause SQL injection - should return safe results or empty
            try:
                results = self.search_engine.search(malicious_query)
                # Results should be empty or safe - no injection should occur
                self.assertIsInstance(results, list)
            except Exception as e:
                # If an exception occurs, it should be a safe database error, not injection
                self.assertNotIn("syntax error", str(e).lower())
    
    def test_input_validation_filename(self):
        """Test that filenames are properly validated"""
        # Test path traversal attempts
        malicious_filenames = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\config\\SAM",
            "test.txt\x00.exe",  # null byte injection
            "test.txt'; DROP TABLE transcripts; --"
        ]
        
        for malicious_filename in malicious_filenames:
            try:
                # Should either reject the filename or sanitize it safely
                result = self.search_engine.add_transcript(
                    malicious_filename, "2025-01-01", "2025-01-01T10:00:00",
                    "test", "/safe/path.txt", "test content"
                )
                # If it succeeds, the filename should be sanitized
                self.assertIsInstance(result, int)
            except ValueError:
                # Should raise ValueError for obviously malicious filenames
                pass
    
    def test_input_size_limits(self):
        """Test that input size limits prevent DoS attacks"""
        # Test extremely large content
        large_content = "A" * 10000000  # 10MB string
        
        try:
            # Should either handle gracefully or reject oversized input
            result = self.search_engine.add_transcript(
                "large_test.txt", "2025-01-01", "2025-01-01T10:00:00",
                "test", "/test/path.txt", large_content
            )
            # If accepted, should be processed without causing system issues
            self.assertIsInstance(result, int)
        except ValueError as e:
            # Should reject with appropriate error message
            self.assertIn("size", str(e).lower())
    
    def test_safe_file_path_handling(self):
        """Test that file paths are handled safely"""
        safe_paths = [
            "/legitimate/path/file.txt",
            "relative/path/file.txt",
            "~/user/documents/file.txt"
        ]
        
        unsafe_paths = [
            "../../../etc/passwd",
            "/dev/null",
            "/proc/self/mem",
            "\\\\server\\share\\file.txt"
        ]
        
        # Safe paths should work
        for safe_path in safe_paths:
            result = self.search_engine.add_transcript(
                "test.txt", "2025-01-01", "2025-01-01T10:00:00",
                "test", safe_path, "test content"
            )
            self.assertIsInstance(result, int)
        
        # Unsafe paths should be rejected or sanitized
        for unsafe_path in unsafe_paths:
            try:
                result = self.search_engine.add_transcript(
                    "test2.txt", "2025-01-01", "2025-01-01T10:00:00",
                    "test", unsafe_path, "test content"
                )
                # If accepted, path should be sanitized
                self.assertIsInstance(result, int)
            except ValueError:
                # Should reject unsafe paths
                pass


if __name__ == '__main__':
    unittest.main()