#!/usr/bin/env python3
"""
Service Reliability Test Script
Tests various failure scenarios for the audio capture service
"""

import os
import sys
import time
import subprocess
import tempfile
import shutil
from pathlib import Path
import json
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_reliability.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('reliability_test')

class ReliabilityTester:
    def __init__(self):
        self.test_results = []
        self.workspace_path = Path(__file__).parent
        
    def log_test_result(self, test_name, passed, message=""):
        """Log test result"""
        status = "PASS" if passed else "FAIL"
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'message': message
        })
        logger.info(f"[{status}] {test_name}: {message}")
    
    def test_path_configuration(self):
        """Test 1: Verify LaunchAgent has correct paths"""
        logger.info("Testing LaunchAgent path configuration...")
        
        try:
            plist_path = Path.home() / "Library/LaunchAgents/com.contextcapture.audio.plist"
            if not plist_path.exists():
                self.log_test_result("Path Configuration", False, "LaunchAgent plist not found")
                return
            
            plist_content = plist_path.read_text()
            workspace_path_str = str(self.workspace_path)
            
            if workspace_path_str in plist_content:
                self.log_test_result("Path Configuration", True, "Workspace paths correctly configured")
            else:
                self.log_test_result("Path Configuration", False, "Workspace paths not found in plist")
                
        except Exception as e:
            self.log_test_result("Path Configuration", False, f"Error: {e}")
    
    def test_permission_detection(self):
        """Test 2: Verify permission checking works"""
        logger.info("Testing permission detection...")
        
        try:
            from audio_capture import AudioCapture
            capture = AudioCapture()
            
            # This should detect the microphone permission issue
            has_permissions = capture.check_permissions()
            
            # We expect this to fail due to microphone permissions
            if not has_permissions:
                self.log_test_result("Permission Detection", True, "Correctly detected permission issues")
            else:
                self.log_test_result("Permission Detection", False, "Should have detected microphone permission issue")
                
        except Exception as e:
            self.log_test_result("Permission Detection", False, f"Error: {e}")
    
    def test_disk_space_monitoring(self):
        """Test 3: Verify disk space monitoring works"""
        logger.info("Testing disk space monitoring...")
        
        try:
            from audio_capture import AudioCapture
            capture = AudioCapture()
            
            # Test disk space check
            result = capture.check_disk_space_and_cleanup(min_free_gb=0.1)  # Very low threshold
            
            if result:
                self.log_test_result("Disk Space Monitoring", True, "Disk space check completed successfully")
            else:
                self.log_test_result("Disk Space Monitoring", False, "Disk space check failed")
                
        except Exception as e:
            self.log_test_result("Disk Space Monitoring", False, f"Error: {e}")
    
    def test_file_cleanup(self):
        """Test 4: Verify file cleanup functionality"""
        logger.info("Testing file cleanup functionality...")
        
        try:
            from audio_capture import AudioCapture
            capture = AudioCapture()
            
            # Create a temporary old file to test cleanup
            temp_path = Path(capture.config["storage"]["temp_path"])
            temp_path.mkdir(parents=True, exist_ok=True)
            
            old_file = temp_path / "test_old_audio.wav"
            old_file.write_text("test audio data")
            
            # Make it appear old by modifying timestamp (45 days ago)
            old_timestamp = time.time() - (45 * 24 * 60 * 60)
            os.utime(old_file, (old_timestamp, old_timestamp))
            
            # Run cleanup
            capture.cleanup_old_files(max_age_days=30)
            
            # Check if file was cleaned up
            if not old_file.exists():
                self.log_test_result("File Cleanup", True, "Old file was successfully cleaned up")
            else:
                self.log_test_result("File Cleanup", False, "Old file was not cleaned up")
                # Clean up manually
                old_file.unlink()
                
        except Exception as e:
            self.log_test_result("File Cleanup", False, f"Error: {e}")
    
    def test_exponential_backoff(self):
        """Test 5: Verify exponential backoff calculation"""
        logger.info("Testing exponential backoff calculation...")
        
        try:
            from audio_capture import AudioCapture
            capture = AudioCapture()
            
            # Test backoff calculation
            delays = []
            for i in range(5):
                capture.failure_count = i
                delay = capture.calculate_backoff_delay()
                delays.append(delay)
            
            # Verify delays increase exponentially
            expected_delays = [0, 10, 20, 40, 80]  # base_delay * 2^(failure_count-1)
            
            if delays == expected_delays:
                self.log_test_result("Exponential Backoff", True, f"Correct delays: {delays}")
            else:
                self.log_test_result("Exponential Backoff", False, f"Expected {expected_delays}, got {delays}")
                
        except Exception as e:
            self.log_test_result("Exponential Backoff", False, f"Error: {e}")
    
    def test_service_status(self):
        """Test 6: Check current service status"""
        logger.info("Testing service status...")
        
        try:
            result = subprocess.run(
                ["launchctl", "list", "com.contextcapture.audio"], 
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                self.log_test_result("Service Status", True, "Service is loaded and responding")
            else:
                self.log_test_result("Service Status", False, "Service is not loaded or not responding")
                
        except Exception as e:
            self.log_test_result("Service Status", False, f"Error: {e}")
    
    def test_config_loading(self):
        """Test 7: Verify configuration loading works"""
        logger.info("Testing configuration loading...")
        
        try:
            from audio_capture import AudioCapture
            capture = AudioCapture()
            
            # Check that config has required keys
            required_keys = ['audio', 'storage']
            missing_keys = [key for key in required_keys if key not in capture.config]
            
            if not missing_keys:
                self.log_test_result("Config Loading", True, "All required config keys present")
            else:
                self.log_test_result("Config Loading", False, f"Missing config keys: {missing_keys}")
                
        except Exception as e:
            self.log_test_result("Config Loading", False, f"Error: {e}")
    
    def run_all_tests(self):
        """Run all reliability tests"""
        logger.info("Starting reliability tests...")
        
        tests = [
            self.test_path_configuration,
            self.test_permission_detection,
            self.test_disk_space_monitoring,
            self.test_file_cleanup,
            self.test_exponential_backoff,
            self.test_service_status,
            self.test_config_loading
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                logger.error(f"Test {test.__name__} failed with exception: {e}")
        
        # Summary
        passed_tests = [r for r in self.test_results if r['passed']]
        failed_tests = [r for r in self.test_results if not r['passed']]
        
        logger.info(f"\n=== RELIABILITY TEST SUMMARY ===")
        logger.info(f"Total tests: {len(self.test_results)}")
        logger.info(f"Passed: {len(passed_tests)}")
        logger.info(f"Failed: {len(failed_tests)}")
        
        if failed_tests:
            logger.info(f"\nFAILED TESTS:")
            for test in failed_tests:
                logger.info(f"  - {test['test']}: {test['message']}")
        
        logger.info(f"\nOverall status: {'PASS' if len(failed_tests) == 0 else 'PARTIAL PASS'}")
        
        return len(failed_tests) == 0

def main():
    tester = ReliabilityTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()