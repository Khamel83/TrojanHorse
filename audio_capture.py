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
from datetime import datetime
from pathlib import Path
import json
import logging

class AudioCapture:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.setup_logging()
        self.running = False
        self.process = None
        
    def load_config(self, config_path):
        """Load configuration or use defaults"""
        default_config = {
            "audio": {
                "chunk_duration": 300,  # 5 minutes
                "sample_rate": 44100,
                "quality": "medium",
                "format": "wav"
            },
            "storage": {
                "temp_path": "/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/MacProAudio",
                "base_path": "/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes"
            }
        }
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                # Merge with defaults
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                return config
        else:
            # Create default config
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
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
        
        # Create temp directory
        temp_dir = Path(self.config["storage"]["temp_path"])
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        while self.running:
            try:
                self.capture_chunk()
                time.sleep(1)  # Small delay between chunks
            except Exception as e:
                self.logger.error(f"Error during capture: {e}")
                time.sleep(10)  # Wait before retrying
    
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

def main():
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