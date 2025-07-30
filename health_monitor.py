#!/usr/bin/env python3
"""
Health Monitor for Context Capture System
Monitors system health and restarts failed services
"""

import os
import sys
import json
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timedelta

class HealthMonitor:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.setup_logging()
        self.service_name = "com.contextcapture.audio"
    
    def load_config(self, config_path):
        """Load configuration"""
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            return {
                "monitoring": {
                    "check_interval": 60,  # seconds
                    "max_restart_attempts": 3,
                    "restart_delay": 30,
                    "health_check_window": 300  # 5 minutes
                }
            }
    
    def setup_logging(self):
        """Setup logging"""
        log_dir = Path("/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Scripting/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "health_monitor.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def check_service_status(self):
        """Check if the audio capture service is running"""
        try:
            result = subprocess.run(
                ["launchctl", "list", self.service_name],
                capture_output=True, text=True, check=False
            )
            
            if result.returncode == 0:
                # Service is loaded, check if it's actually running
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'PID' in line or line.strip().isdigit():
                        return True, "running"
                return True, "loaded_not_running"
            else:
                return False, "not_loaded"
                
        except Exception as e:
            self.logger.error(f"Failed to check service status: {e}")
            return False, "error"
    
    def check_audio_files_recent(self):
        """Check if audio files are being created recently"""
        try:
            temp_path = Path(self.config.get("storage", {}).get("temp_path", 
                            "/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/MacProAudio"))
            
            if not temp_path.exists():
                return False, "temp_directory_missing"
            
            # Check for files created in the last 10 minutes
            cutoff_time = datetime.now() - timedelta(minutes=10)
            recent_files = []
            
            for audio_file in temp_path.glob("*.wav"):
                if datetime.fromtimestamp(audio_file.stat().st_mtime) > cutoff_time:
                    recent_files.append(audio_file)
            
            if recent_files:
                return True, f"found_{len(recent_files)}_recent_files"
            else:
                return False, "no_recent_files"
                
        except Exception as e:
            self.logger.error(f"Failed to check recent audio files: {e}")
            return False, "error"
    
    def check_disk_space(self):
        """Check available disk space"""
        try:
            base_path = Path(self.config.get("storage", {}).get("base_path", 
                            "/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes"))
            
            if not base_path.exists():
                return False, "base_directory_missing"
            
            # Get disk usage
            statvfs = os.statvfs(str(base_path))
            free_bytes = statvfs.f_frsize * statvfs.f_bavail
            free_gb = free_bytes / (1024**3)
            
            if free_gb < 1.0:  # Less than 1GB free
                return False, f"low_disk_space_{free_gb:.1f}GB"
            else:
                return True, f"disk_space_ok_{free_gb:.1f}GB"
                
        except Exception as e:
            self.logger.error(f"Failed to check disk space: {e}")
            return False, "error"
    
    def restart_service(self):
        """Restart the audio capture service"""
        try:
            plist_path = Path.home() / "Library/LaunchAgents/com.contextcapture.audio.plist"
            
            # Unload service
            subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
            time.sleep(5)
            
            # Reload service
            result = subprocess.run(["launchctl", "load", str(plist_path)], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info("Service restarted successfully")
                return True
            else:
                self.logger.error(f"Failed to restart service: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to restart service: {e}")
            return False
    
    def send_notification(self, title, message):
        """Send macOS notification"""
        try:
            cmd = [
                "osascript", "-e",
                f'display notification "{message}" with title "{title}"'
            ]
            subprocess.run(cmd, check=False)
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
    
    def run_health_check(self):
        """Run a complete health check"""
        issues = []
        
        # Check service status
        service_ok, service_status = self.check_service_status()
        if not service_ok:
            issues.append(f"Service issue: {service_status}")
        
        # Check recent audio files
        files_ok, files_status = self.check_audio_files_recent()
        if not files_ok:
            issues.append(f"Audio files issue: {files_status}")
        
        # Check disk space
        disk_ok, disk_status = self.check_disk_space()
        if not disk_ok:
            issues.append(f"Disk space issue: {disk_status}")
        
        if issues:
            self.logger.warning(f"Health check failed: {', '.join(issues)}")
            return False, issues
        else:
            self.logger.info("Health check passed")
            return True, []
    
    def monitor_loop(self):
        """Main monitoring loop"""
        restart_attempts = 0
        max_attempts = self.config.get("monitoring", {}).get("max_restart_attempts", 3)
        check_interval = self.config.get("monitoring", {}).get("check_interval", 60)
        restart_delay = self.config.get("monitoring", {}).get("restart_delay", 30)
        
        self.logger.info("Starting health monitor")
        
        while True:
            try:
                healthy, issues = self.run_health_check()
                
                if not healthy:
                    self.logger.warning("System unhealthy, attempting restart")
                    
                    if restart_attempts < max_attempts:
                        if self.restart_service():
                            restart_attempts = 0  # Reset counter on successful restart
                            self.send_notification("Context Capture", "Service restarted")
                            time.sleep(restart_delay)
                        else:
                            restart_attempts += 1
                            self.logger.error(f"Restart attempt {restart_attempts}/{max_attempts} failed")
                    else:
                        self.logger.error("Max restart attempts reached, giving up")
                        self.send_notification("Context Capture", "Service failed - manual intervention required")
                        break
                else:
                    restart_attempts = 0  # Reset counter when healthy
                
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Health monitor stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
                time.sleep(check_interval)
    
    def status_report(self):
        """Generate status report"""
        print("Context Capture System Status Report")
        print("=" * 40)
        
        # Service status
        service_ok, service_status = self.check_service_status()
        print(f"Service Status: {'✓' if service_ok else '✗'} {service_status}")
        
        # Recent files
        files_ok, files_status = self.check_audio_files_recent()
        print(f"Recent Audio Files: {'✓' if files_ok else '✗'} {files_status}")
        
        # Disk space
        disk_ok, disk_status = self.check_disk_space()
        print(f"Disk Space: {'✓' if disk_ok else '✗'} {disk_status}")
        
        # Overall health
        healthy, issues = self.run_health_check()
        print(f"Overall Health: {'✓' if healthy else '✗'} {'Healthy' if healthy else 'Issues detected'}")
        
        if issues:
            print("\nIssues:")
            for issue in issues:
                print(f"  - {issue}")

def main():
    monitor = HealthMonitor()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "status":
            monitor.status_report()
        elif command == "check":
            healthy, issues = monitor.run_health_check()
            if healthy:
                print("✓ System is healthy")
            else:
                print("✗ System has issues:")
                for issue in issues:
                    print(f"  - {issue}")
                sys.exit(1)
        elif command == "restart":
            if monitor.restart_service():
                print("✓ Service restarted successfully")
            else:
                print("✗ Failed to restart service")
                sys.exit(1)
        elif command == "monitor":
            monitor.monitor_loop()
        else:
            print("Usage: python3 health_monitor.py [status|check|restart|monitor]")
            sys.exit(1)
    else:
        # Default to status report
        monitor.status_report()

if __name__ == "__main__":
    main()