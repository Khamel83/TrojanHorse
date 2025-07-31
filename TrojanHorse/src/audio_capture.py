#!/usr/bin/env python3
"""
Audio Capture Module for Context Capture System
Continuously records mic + system audio in 5-minute chunks
"""

import os
import sys
import time
import subprocess
import signal
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging
import shutil

from config_manager import ConfigManager

class AudioCapture:
    def __init__(self, config_path="config.json"):
        self.config = ConfigManager(config_path=config_path).config
    
    def setup_logging(self):
        """Setup logging to daily folder"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_dir = Path(self.config["storage"]["base_path"]) / today
        log_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "capture.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def get_audio_devices(self):
        """Get available audio input devices"""
        try:
            result = subprocess.run(['ffmpeg', '-hide_banner', '-f', 'avfoundation', '-list_devices', 'true', '-i', ''],
                                  capture_output=True, text=True)
            output = result.stderr  # FFmpeg sends device list to stderr
            self.logger.info("Available audio devices:")
            self.logger.info(output)
            print(output)  # Also print to console
            return output
        except Exception as e:
            self.logger.error(f"Failed to list audio devices: {e}")
            return None
    
    def start_capture(self):
        """Start continuous audio capture"""
        self.running = True
        self.logger.info("Starting audio capture...")
        
        # Check permissions before starting
        if not self.check_permissions():
            self.logger.error("Cannot start due to permission issues. Please fix permissions and restart.")
            sys.exit(1)
        
        # Create temp directory
        temp_dir = Path(self.config["storage"]["temp_path"])
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        while self.running:
            try:
                # Check disk space periodically
                current_time = time.time()
                if current_time - self.last_cleanup_check > self.cleanup_check_interval:
                    self.logger.info("Performing periodic disk space check")
                    if not self.check_disk_space_and_cleanup():
                        self.logger.error("Disk space check failed, continuing anyway")
                    self.last_cleanup_check = current_time
                
                self.capture_chunk()
                self.reset_failure_count()  # Reset on successful capture
                time.sleep(1)  # Small delay between chunks
            except Exception as e:
                self.failure_count += 1
                self.logger.error(f"Error during capture (failure #{self.failure_count}): {e}")
                
                # Check if we've exceeded max failures
                if self.failure_count >= self.max_failures:
                    self.logger.critical(f"Exceeded max failures ({self.max_failures}), exiting")
                    break
                
                # Calculate exponential backoff delay
                delay = self.calculate_backoff_delay()
                self.logger.info(f"Waiting {delay} seconds before retry (failure #{self.failure_count})")
                time.sleep(delay)
    
    def capture_chunk(self):
        """Capture a single audio chunk"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_file = Path(self.config["storage"]["temp_path"]) / f"audio_{timestamp}.wav"
        
        # FFmpeg command for capturing microphone audio
        # Using MacBook Pro Microphone (index 0) for now
        # To add system audio later, install BlackHole and update to use both inputs
        cmd = [
            'ffmpeg',
            '-f', 'avfoundation',
            '-i', ':0',  # MacBook Pro Microphone
            '-t', str(self.config["audio"]["chunk_duration"]),
            '-acodec', 'pcm_s16le',
            '-ar', str(self.config["audio"]["sample_rate"]),
            str(temp_file),
            '-y'  # Overwrite without asking
        ]
        
        self.logger.info(f"Starting capture: {temp_file}")
        
        try:
            self.process = subprocess.Popen(cmd, 
                                          stdout=subprocess.PIPE, 
                                          stderr=subprocess.PIPE)
            stdout, stderr = self.process.communicate()
            
            if self.process.returncode == 0:
                self.logger.info(f"Capture completed: {temp_file}")
                self.move_to_daily_folder(temp_file)
            else:
                self.logger.error(f"FFmpeg error: {stderr.decode()}")
                
        except Exception as e:
            self.logger.error(f"Failed to capture audio: {e}")
            if self.process:
                self.process.terminate()
    
    def move_to_daily_folder(self, temp_file):
        """Move completed audio file to daily folder structure"""
        today = datetime.now().strftime("%Y-%m-%d")
        daily_dir = Path(self.config["storage"]["base_path"]) / today / "transcribed_audio"
        daily_dir.mkdir(parents=True, exist_ok=True)
        
        dest_file = daily_dir / temp_file.name
        
        try:
            temp_file.rename(dest_file)
            self.logger.info(f"Moved audio file to: {dest_file}")
            
            # Trigger transcription (async)
            self.trigger_transcription(dest_file)
            
        except Exception as e:
            self.logger.error(f"Failed to move audio file: {e}")
    
    def trigger_transcription(self, audio_file):
        """Trigger transcription in background"""
        try:
            # Start transcription process in background
            cmd = [sys.executable, "transcribe.py", str(audio_file)]
            subprocess.Popen(cmd)
            self.logger.info(f"Triggered transcription for: {audio_file}")
        except Exception as e:
            self.logger.error(f"Failed to trigger transcription: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        if self.process:
            self.process.terminate()
        sys.exit(0)
    
    def stop_capture(self):
        """Stop audio capture"""
        self.running = False
        if self.process:
            self.process.terminate()
        self.logger.info("Audio capture stopped")
    
    def calculate_backoff_delay(self):
        """Calculate exponential backoff delay"""
        if self.failure_count == 0:
            return 0
        
        # Exponential backoff: base_delay * 2^(failure_count-1)
        # With max delay of 5 minutes (300 seconds)
        delay = self.base_delay * (2 ** (self.failure_count - 1))
        max_delay = 300  # 5 minutes
        return min(delay, max_delay)
    
    def reset_failure_count(self):
        """Reset failure count on successful operation"""
        if self.failure_count > 0:
            self.logger.info(f"Resetting failure count from {self.failure_count} to 0")
            self.failure_count = 0
    
    def get_disk_space(self, path):
        """Get available disk space in bytes"""
        try:
            stat = shutil.disk_usage(path)
            return stat.free, stat.total
        except Exception as e:
            self.logger.error(f"Failed to get disk space for {path}: {e}")
            return 0, 0
    
    def cleanup_old_files(self, max_age_days=30):
        """Clean up audio files older than max_age_days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            cleanup_count = 0
            space_freed = 0
            
            # Check both temp and base paths
            paths_to_check = [
                Path(self.config["storage"]["temp_path"]),
                Path(self.config["storage"]["base_path"])
            ]
            
            for base_path in paths_to_check:
                if not base_path.exists():
                    continue
                
                # Find audio files older than cutoff date
                for file_path in base_path.rglob("*.wav"):
                    try:
                        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_mtime < cutoff_date:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            cleanup_count += 1
                            space_freed += file_size
                            self.logger.info(f"Deleted old audio file: {file_path}")
                    except Exception as e:
                        self.logger.error(f"Failed to delete {file_path}: {e}")
            
            if cleanup_count > 0:
                space_freed_mb = space_freed / (1024 * 1024)
                self.logger.info(f"Cleanup complete: removed {cleanup_count} files, freed {space_freed_mb:.1f} MB")
            else:
                self.logger.info("No old files found for cleanup")
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def check_permissions(self):
        """Check for required permissions and provide clear error messages"""
        permission_issues = []
        
        try:
            # Check microphone permission by attempting to list audio devices
            cmd = ['ffmpeg', '-f', 'avfoundation', '-list_devices', 'true', '-i', '""']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # FFmpeg outputs device list to stderr, check both stdout and stderr
            output_text = result.stdout + result.stderr
            if "AVCaptureDeviceTypeBuiltInMicrophone" not in output_text:
                permission_issues.append({
                    'type': 'microphone',
                    'message': 'Microphone access denied. Grant microphone permission in System Preferences > Security & Privacy > Privacy > Microphone',
                    'critical': True
                })
            else:
                self.logger.info("✓ Microphone permission verified")
                
        except Exception as e:
            permission_issues.append({
                'type': 'microphone',
                'message': f'Unable to verify microphone permissions: {e}',
                'critical': True
            })
        
        try:
            # Check file system access by trying to create a test file
            test_paths = [
                Path(self.config["storage"]["temp_path"]),
                Path(self.config["storage"]["base_path"])
            ]
            
            for test_path in test_paths:
                test_file = test_path / "permission_test.txt"
                try:
                    test_path.mkdir(parents=True, exist_ok=True)
                    test_file.write_text("permission test")
                    test_file.unlink()
                    self.logger.info(f"✓ File system access verified for {test_path}")
                except Exception as e:
                    permission_issues.append({
                        'type': 'filesystem',
                        'message': f'File system access denied for {test_path}. Grant Full Disk Access in System Preferences > Security & Privacy > Privacy > Full Disk Access',
                        'critical': True,
                        'path': str(test_path)
                    })
                    
        except Exception as e:
            permission_issues.append({
                'type': 'filesystem',
                'message': f'Unable to verify file system permissions: {e}',
                'critical': True
            })
        
        # Report permission issues
        if permission_issues:
            self.logger.error("❌ Permission issues detected:")
            for issue in permission_issues:
                if issue['critical']:
                    self.logger.error(f"  CRITICAL: {issue['message']}")
                else:
                    self.logger.warning(f"  WARNING: {issue['message']}")
            
            # Provide consolidated help message
            self.logger.error("\n🔧 To fix permission issues:")
            self.logger.error("1. Open System Preferences > Security & Privacy > Privacy")
            self.logger.error("2. Click 'Microphone' and ensure this app/terminal is checked")
            self.logger.error("3. Click 'Full Disk Access' and add your terminal app")
            self.logger.error("4. Restart the service after granting permissions")
            
            return False
        else:
            self.logger.info("✅ All permissions verified successfully")
            return True
    
    def check_disk_space_and_cleanup(self, min_free_gb=1.0):
        """Check disk space and cleanup if needed"""
        try:
            # Check space in base path (where final files are stored)
            base_path = Path(self.config["storage"]["base_path"])
            free_bytes, total_bytes = self.get_disk_space(base_path)
            
            if free_bytes == 0:  # Error getting disk space
                return False
            
            free_gb = free_bytes / (1024**3)
            total_gb = total_bytes / (1024**3)
            used_percent = ((total_bytes - free_bytes) / total_bytes) * 100
            
            self.logger.info(f"Disk space: {free_gb:.1f} GB free of {total_gb:.1f} GB ({used_percent:.1f}% used)")
            
            # If less than min_free_gb available, do cleanup
            if free_gb < min_free_gb:
                self.logger.warning(f"Low disk space ({free_gb:.1f} GB), starting cleanup")
                self.cleanup_old_files(max_age_days=30)
                
                # Check space again after cleanup
                free_bytes_after, _ = self.get_disk_space(base_path)
                free_gb_after = free_bytes_after / (1024**3)
                
                if free_gb_after < min_free_gb:
                    self.logger.warning(f"Still low on space after cleanup ({free_gb_after:.1f} GB)")
                    return False
                else:
                    self.logger.info(f"Cleanup successful, now have {free_gb_after:.1f} GB free")
                    return True
            else:
                return True
                
        except Exception as e:
            self.logger.error(f"Error checking disk space: {e}")
            return False

from config_manager import ConfigManager

def main():
    try:
        config_manager = ConfigManager()
        config_manager.validate_config()
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    capture = AudioCapture()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--list-devices":
        capture.get_audio_devices()
        return
    
    try:
        capture.start_capture()
    except KeyboardInterrupt:
        capture.stop_capture()

if __name__ == "__main__":
    main()