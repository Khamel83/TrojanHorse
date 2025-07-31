#!/usr/bin/env python3
"""
Unit tests for ConfigManager
"""

import unittest
import tempfile
import json
import os
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config_manager import ConfigManager


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.json')
        
        # Create a valid test config
        self.test_config = {
            "audio": {"chunk_duration": 300},
            "storage": {"base_path": self.temp_dir},
            "transcription": {"engine": "test"},
            "analysis": {"default_mode": "local"},
            "prompts": {"local_analysis_file": "test.txt"}
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(self.test_config, f)
    
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        os.rmdir(self.temp_dir)
    
    def test_load_config(self):
        """Test configuration loading"""
        config_manager = ConfigManager(self.config_file)
        self.assertEqual(config_manager.get_value("audio.chunk_duration"), 300)
        self.assertEqual(config_manager.get_value("storage.base_path"), self.temp_dir)
    
    def test_get_value(self):
        """Test getting configuration values"""
        config_manager = ConfigManager(self.config_file)
        
        # Test valid keys
        self.assertEqual(config_manager.get_value("audio.chunk_duration"), 300)
        self.assertEqual(config_manager.get_value("transcription.engine"), "test")
        
        # Test invalid keys
        self.assertIsNone(config_manager.get_value("nonexistent.key"))
        self.assertIsNone(config_manager.get_value("audio.nonexistent"))
    
    def test_set_value(self):
        """Test setting configuration values"""
        config_manager = ConfigManager(self.config_file)
        
        # Test setting existing value
        self.assertTrue(config_manager.set_value("audio.chunk_duration", 600))
        self.assertEqual(config_manager.get_value("audio.chunk_duration"), 600)
        
        # Test setting new nested value
        self.assertTrue(config_manager.set_value("new.nested.value", "test"))
        self.assertEqual(config_manager.get_value("new.nested.value"), "test")
    
    def test_validate_config(self):
        """Test configuration validation"""
        config_manager = ConfigManager(self.config_file)
        
        # Should pass validation
        try:
            config_manager.validate_config()
        except ValueError:
            self.fail("validate_config() raised ValueError unexpectedly")
        
        # Test invalid configuration
        config_manager.set_value("audio.chunk_duration", "invalid")
        with self.assertRaises(ValueError):
            config_manager.validate_config()


if __name__ == '__main__':
    unittest.main()