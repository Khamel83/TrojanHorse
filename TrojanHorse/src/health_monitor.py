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
from config_manager import ConfigManager
from search_engine import SearchEngine
from analytics_engine import AnalyticsEngine

class HealthMonitor:
    def __init__(self, config_path="config.json"):
        self.config = ConfigManager(config_path=config_path).config
        self.setup_logging()
        self.services = {
            "audio_capture": {"path": "src/audio_capture.py", "process": None, "status": "stopped"},
            "internal_api": {"path": "src/internal_api.py", "process": None, "status": "stopped"},
            "hotkey_client": {"path": "src/hotkey_client.py", "process": None, "status": "stopped"}
        }
        self.service_pids = {} # To store PIDs for external management if needed

    def check_service_status(self, service_name: str) -> str:
        service = self.services[service_name]
        if service["process"] and service["process"].poll() is None:
            return "running"
        return "stopped"

    def _start_service(self, service_name: str) -> bool:
        service = self.services[service_name]
        if self.check_service_status(service_name) == "running":
            self.logger.info(f"{service_name} is already running.")
            return True
        
        try:
            # Use sys.executable to ensure the correct python interpreter is used
            cmd = [sys.executable, service["path"]]
            
            # For internal_api and hotkey_client, they should run in background
            # For audio_capture, it's typically managed by launchd, but for direct start, it also runs in background
            service["process"] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
            self.logger.info(f"Started {service_name} with PID {service['process'].pid}")
            service["status"] = "running"
            return True
        except Exception as e:
            self.logger.error(f"Failed to start {service_name}: {e}")
            service["status"] = "failed"
            return False

    def _stop_service(self, service_name: str) -> bool:
        service = self.services[service_name]
        if self.check_service_status(service_name) == "stopped":
            self.logger.info(f"{service_name} is already stopped.")
            return True
        
        try:
            if service["process"]:
                # Terminate the process group to ensure all child processes are killed
                os.killpg(os.getpgid(service["process"].pid), signal.SIGTERM)
                service["process"].wait(timeout=5) # Wait for process to terminate
            self.logger.info(f"Stopped {service_name}")
            service["status"] = "stopped"
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop {service_name}: {e}")
            service["status"] = "failed"
            return False

    def setup_logging(self):
        """Setup logging"""
        log_dir = Path("logs")
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
    
    def check_analysis_capabilities(self):
        """Check analysis pipeline capabilities"""
        try:
            # Try to import and check analysis router
            from analysis_router import AnalysisRouter
            
            router = AnalysisRouter()
            stats = router.get_analysis_stats()
            
            local_available = stats.get("local_available", False)
            cloud_available = stats.get("cloud_available", False)
            
            if not local_available and not cloud_available:
                return False, "no_analysis_available"
            elif local_available and cloud_available:
                return True, "both_local_and_cloud_available"
            elif local_available:
                return True, f"local_available_{stats.get('local_model', 'unknown')}"
            else:
                return True, f"cloud_available_{stats.get('cloud_model', 'unknown')}"
                
        except ImportError as e:
            self.logger.error(f"Analysis router not available: {e}")
            return False, "analysis_router_missing"
        except Exception as e:
            self.logger.error(f"Failed to check analysis capabilities: {e}")
            return False, "analysis_check_error"
    
    def check_analysis_recent(self):
        """Check if analysis files are being created recently"""
        try:
            base_path = Path(self.config.get("storage", {}).get("base_path", 
                            "/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes"))
            
            if not base_path.exists():
                return False, "base_directory_missing"
            
            # Check for analysis files created in the last 60 minutes
            cutoff_time = datetime.now() - timedelta(minutes=60)
            recent_analyses = []
            
            # Look for .analysis.md files
            for analysis_file in base_path.rglob("*.analysis.md"):
                if datetime.fromtimestamp(analysis_file.stat().st_mtime) > cutoff_time:
                    recent_analyses.append(analysis_file)
            
            if recent_analyses:
                return True, f"found_{len(recent_analyses)}_recent_analyses"
            else:
                # Check if there are recent transcripts that should have been analyzed
                recent_transcripts = []
                for transcript_file in base_path.rglob("*.txt"):
                    if datetime.fromtimestamp(transcript_file.stat().st_mtime) > cutoff_time:
                        # Skip log files and other non-transcript files
                        if not any(skip in transcript_file.name.lower() for skip in 
                                 ['log', 'config', 'readme', 'summary']):
                            recent_transcripts.append(transcript_file)
                
                if recent_transcripts:
                    return False, f"no_recent_analyses_but_{len(recent_transcripts)}_recent_transcripts"
                else:
                    return True, "no_recent_transcripts_or_analyses"
                
        except Exception as e:
            self.logger.error(f"Failed to check recent analyses: {e}")
            return False, "error"
    
    def start_all_services(self):
        self.logger.info("Starting all services...")
        # Start internal_api first as hotkey_client depends on it
        self._start_service("internal_api")
        self._start_service("audio_capture")
        self._start_service("hotkey_client")

    def stop_all_services(self):
        self.logger.info("Stopping all services...")
        self._stop_service("hotkey_client")
        self._stop_service("audio_capture")
        self._stop_service("internal_api")

    def restart_all_services(self):
        self.logger.info("Restarting all services...")
        self.stop_all_services()
        time.sleep(5) # Give time for processes to fully terminate
        self.start_all_services()

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
        
        # Check status of all managed services
        for service_name in self.services:
            status = self.check_service_status(service_name)
            if status != "running":
                issues.append(f"Service {service_name} is {status}")

        # Check recent audio files
        files_ok, files_status = self.check_audio_files_recent()
        if not files_ok:
            issues.append(f"Audio files issue: {files_status}")
        
        # Check disk space
        disk_ok, disk_status = self.check_disk_space()
        if not disk_ok:
            issues.append(f"Disk space issue: {disk_status}")
        
        # Check analysis capabilities
        analysis_ok, analysis_status = self.check_analysis_capabilities()
        if not analysis_ok:
            issues.append(f"Analysis capabilities issue: {analysis_status}")
        
        # Check recent analysis activity (only if capabilities are OK)
        if analysis_ok:
            analysis_recent_ok, analysis_recent_status = self.check_analysis_recent()
            if not analysis_recent_ok:
                issues.append(f"Analysis activity issue: {analysis_recent_status}")
        
        if issues:
            self.logger.warning(f"Health check failed: {', '.join(issues)}")
            return False, issues
        else:
            self.logger.info("Health check passed")
            return True, []
    
    def monitor_loop(self):
        """Main monitoring loop"""
        check_interval = self.config.get("monitoring", {}).get("check_interval", 60)
        
        self.logger.info("Starting health monitor")
        
        while True:
            try:
                healthy, issues = self.run_health_check()
                
                if not healthy:
                    self.logger.warning("System unhealthy, attempting to restart services")
                    self.restart_all_services()
                    self.send_notification("Context Capture", "Services restarted due to unhealthiness")
                
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Health monitor stopped by user")
                self.stop_all_services()
                break
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
                time.sleep(check_interval)
    
    def status_report(self):
        """Generate status report"""
        print("Context Capture System Status Report")
        print("=" * 40)
        
        for service_name, service_info in self.services.items():
            status = self.check_service_status(service_name)
            print(f"Service '{service_name}': {'✓' if status == 'running' else '✗'} {status}")

        # Original checks (audio files, disk space, analysis capabilities, etc.)
        # These still apply to the overall system health
        
        # Check recent files
        files_ok, files_status = self.check_audio_files_recent()
        print(f"Recent Audio Files: {'✓' if files_ok else '✗'} {files_status}")
        
        # Disk space
        disk_ok, disk_status = self.check_disk_space()
        print(f"Disk Space: {'✓' if disk_ok else '✗'} {disk_status}")
        
        # Analysis capabilities
        analysis_ok, analysis_status = self.check_analysis_capabilities()
        print(f"Analysis Capabilities: {'✓' if analysis_ok else '✗'} {analysis_status}")
        
        # Analysis activity (only if capabilities are OK)
        if analysis_ok:
            analysis_recent_ok, analysis_recent_status = self.check_analysis_recent()
            print(f"Analysis Activity: {'✓' if analysis_recent_ok else '✗'} {analysis_recent_status}")
        
        # Overall health (simplified for now, can be expanded)
        overall_healthy = all(self.check_service_status(s) == "running" for s in self.services) and \
                          files_ok and disk_ok and analysis_ok and analysis_recent_ok
        print(f"Overall Health: {'✓' if overall_healthy else '✗'} {'Healthy' if overall_healthy else 'Issues detected'}")

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
        elif command == "start":
            monitor.start_all_services()
        elif command == "stop":
            monitor.stop_all_services()
        elif command == "restart":
            monitor.restart_all_services()
        elif command == "monitor":
            monitor.monitor_loop()
        elif command == "optimize":
            search_engine = SearchEngine(monitor.config.get('db_path', 'trojan_search.db'))
            search_engine.optimize_database()
            search_engine.close()
        elif command == "analyze":
            analytics_engine = AnalyticsEngine(monitor.config.get('db_path', 'trojan_search.db'))
            analytics_engine.run_full_analysis()
            analytics_engine.calculate_trends()
            analytics_engine.close()
        else:
            print("Usage: python3 health_monitor.py [status|check|start|stop|restart|monitor|optimize|analyze]")
            sys.exit(1)
    else:
        # Default to status report
        monitor.status_report()

if __name__ == "__main__":
    main()