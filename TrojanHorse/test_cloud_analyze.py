"""
Tests for cloud_analyze.py module.

This test suite validates the cloud analysis functionality including
configuration loading, API integration, and error handling.
"""

import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import patch, Mock, mock_open
import requests

# Import the module to test
from cloud_analyze import load_config, analyze, test_connection


class TestCloudAnalyze(unittest.TestCase):
    """Test cases for cloud analysis functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_config = {
            "cloud_analysis": {
                "openrouter_api_key": "test-key-12345",
                "model": "google/gemini-2.0-flash-001",
                "base_url": "https://openrouter.ai/api/v1"
            }
        }
        
        self.sample_text = "The team discussed project milestones and budget allocation."
        self.sample_prompt = "Summarize the key points from this meeting."
        
    def test_load_config_success(self):
        """Test successful configuration loading."""
        with patch('builtins.open', mock_open(read_data=json.dumps(self.test_config))):
            config = load_config()
            self.assertEqual(config['cloud_analysis']['openrouter_api_key'], 'test-key-12345')
            self.assertEqual(config['cloud_analysis']['model'], 'google/gemini-2.0-flash-001')
            
    def test_load_config_file_not_found(self):
        """Test configuration loading when file doesn't exist."""
        with patch('builtins.open', side_effect=FileNotFoundError()):
            with self.assertRaises(FileNotFoundError):
                load_config()
                
    def test_load_config_invalid_json(self):
        """Test configuration loading with invalid JSON."""
        with patch('builtins.open', mock_open(read_data='invalid json')):
            with self.assertRaises(ValueError):
                load_config()
                
    @patch('cloud_analyze.load_config')
    @patch('requests.post')
    def test_analyze_success(self, mock_post, mock_load_config):
        """Test successful analysis with API."""
        # Mock configuration
        mock_load_config.return_value = self.test_config
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'Key points: milestones and budget discussed.'
                }
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = analyze(self.sample_text, self.sample_prompt)
        
        self.assertEqual(result, 'Key points: milestones and budget discussed.')
        mock_post.assert_called_once()
        
        # Verify the API call parameters
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], 'https://openrouter.ai/api/v1/chat/completions')
        self.assertIn('Authorization', call_args[1]['headers'])
        self.assertEqual(call_args[1]['headers']['Authorization'], 'Bearer test-key-12345')
        
    @patch('cloud_analyze.load_config')
    def test_analyze_missing_api_key(self, mock_load_config):
        """Test analysis with missing API key."""
        config_no_key = {
            "cloud_analysis": {
                "openrouter_api_key": "YOUR_OPENROUTER_API_KEY_HERE",
                "model": "google/gemini-2.0-flash-001"
            }
        }
        mock_load_config.return_value = config_no_key
        
        with self.assertRaises(ValueError) as context:
            analyze(self.sample_text, self.sample_prompt)
            
        self.assertIn("API key not configured", str(context.exception))
        
    @patch('cloud_analyze.load_config')
    @patch('requests.post')
    def test_analyze_api_error_401(self, mock_post, mock_load_config):
        """Test analysis with API authentication error."""
        mock_load_config.return_value = self.test_config
        
        # Mock 401 error response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError()
        
        with self.assertRaises(ValueError) as context:
            analyze(self.sample_text, self.sample_prompt)
            
        self.assertIn("Invalid API key", str(context.exception))
        
    @patch('cloud_analyze.load_config')
    @patch('requests.post')
    def test_analyze_api_error_429(self, mock_post, mock_load_config):
        """Test analysis with rate limit error."""
        mock_load_config.return_value = self.test_config
        
        # Mock 429 error response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response
        mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError()
        
        with self.assertRaises(requests.RequestException) as context:
            analyze(self.sample_text, self.sample_prompt)
            
        self.assertIn("Rate limit exceeded", str(context.exception))
        
    @patch('cloud_analyze.load_config')
    @patch('requests.post')
    def test_analyze_timeout(self, mock_post, mock_load_config):
        """Test analysis with request timeout."""
        mock_load_config.return_value = self.test_config
        mock_post.side_effect = requests.exceptions.Timeout()
        
        with self.assertRaises(requests.RequestException) as context:
            analyze(self.sample_text, self.sample_prompt)
            
        self.assertIn("Request timed out", str(context.exception))
        
    @patch('cloud_analyze.load_config')
    @patch('requests.post')
    def test_analyze_connection_error(self, mock_post, mock_load_config):
        """Test analysis with connection error."""
        mock_load_config.return_value = self.test_config
        mock_post.side_effect = requests.exceptions.ConnectionError()
        
        with self.assertRaises(requests.RequestException) as context:
            analyze(self.sample_text, self.sample_prompt)
            
        self.assertIn("Connection error", str(context.exception))
        
    @patch('cloud_analyze.load_config')
    @patch('requests.post')
    def test_analyze_invalid_response_format(self, mock_post, mock_load_config):
        """Test analysis with invalid API response format."""
        mock_load_config.return_value = self.test_config
        
        # Mock response with missing choices
        mock_response = Mock()
        mock_response.json.return_value = {'error': 'Invalid request'}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        with self.assertRaises(ValueError) as context:
            analyze(self.sample_text, self.sample_prompt)
            
        self.assertIn("Invalid response format", str(context.exception))
        
    @patch('cloud_analyze.analyze')
    def test_connection_success(self, mock_analyze):
        """Test successful connection test."""
        mock_analyze.return_value = "OK"
        
        result = test_connection()
        self.assertTrue(result)
        
    @patch('cloud_analyze.analyze')
    def test_connection_failure(self, mock_analyze):
        """Test failed connection test."""
        mock_analyze.side_effect = ValueError("API key not configured")
        
        result = test_connection()
        self.assertFalse(result)
        
    @patch('cloud_analyze.load_config')
    @patch('requests.post')
    def test_analyze_message_format(self, mock_post, mock_load_config):
        """Test that messages are formatted correctly for the API."""
        mock_load_config.return_value = self.test_config
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'Test response'
                }
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        analyze(self.sample_text, self.sample_prompt)
        
        # Verify the message format in the API call
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        
        self.assertEqual(len(payload['messages']), 2)
        self.assertEqual(payload['messages'][0]['role'], 'system')
        self.assertEqual(payload['messages'][0]['content'], self.sample_prompt)
        self.assertEqual(payload['messages'][1]['role'], 'user')
        self.assertEqual(payload['messages'][1]['content'], self.sample_text)
        

class TestIntegration(unittest.TestCase):
    """Integration tests that require actual API connectivity."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        # Only run if we have a real config file
        try:
            config = load_config()
            api_key = config.get('cloud_analysis', {}).get('openrouter_api_key')
            if not api_key or api_key == "YOUR_OPENROUTER_API_KEY_HERE":
                self.skipTest("No valid API key configured for integration tests")
        except FileNotFoundError:
            self.skipTest("No config file found for integration tests")
            
    def test_real_api_connection(self):
        """Test actual API connection (requires valid API key)."""
        result = test_connection()
        self.assertTrue(result, "API connection failed with real credentials")
        
    def test_real_analysis(self):
        """Test actual analysis with real API (requires valid API key)."""
        test_text = "The quarterly review meeting covered sales performance and marketing strategy."
        test_prompt = "Extract the main topics discussed in this meeting."
        
        result = analyze(test_text, test_prompt)
        
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 10)  # Should get a meaningful response
        self.assertIn("sales", result.lower())  # Should mention sales from the input


if __name__ == '__main__':
    # Run tests with different verbosity based on arguments
    import sys
    
    if '--integration' in sys.argv:
        # Run integration tests only
        suite = unittest.TestLoader().loadTestsFromTestCase(TestIntegration)
        sys.argv.remove('--integration')
    elif '--unit' in sys.argv:
        # Run unit tests only
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCloudAnalyze)
        sys.argv.remove('--unit')
    else:
        # Run all tests
        suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)