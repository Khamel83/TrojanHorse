#!/usr/bin/env python3
"""
Setup script for Context Capture System
Creates folder structure and installs service
"""

import os
import sys
import subprocess
from pathlib import Path
import json

def create_folder_structure():
    """Create the daily folder structure"""
    base_path = Path("/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes")
    temp_path = Path("/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/MacProAudio")
    logs_path = Path("/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Scripting/logs")
    
    # Create directories
    for path in [base_path, temp_path, logs_path]:
        path.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {path}")
    
    return True

def install_service():
    """Install the launchd service"""
    plist_source = Path("com.contextcapture.audio.plist")
    plist_dest = Path.home() / "Library/LaunchAgents/com.contextcapture.audio.plist"
    
    try:
        # Copy plist file
        plist_dest.parent.mkdir(exist_ok=True)
        plist_dest.write_text(plist_source.read_text())
        print(f"Installed service plist: {plist_dest}")
        
        # Load the service
        subprocess.run(["launchctl", "load", str(plist_dest)], check=True)
        print("Service loaded successfully")
        
        return True
    except Exception as e:
        print(f"Failed to install service: {e}")
        return False

def uninstall_service():
    """Uninstall the launchd service"""
    plist_dest = Path.home() / "Library/LaunchAgents/com.contextcapture.audio.plist"
    
    try:
        # Unload the service
        subprocess.run(["launchctl", "unload", str(plist_dest)], check=False)
        print("Service unloaded")
        
        # Remove plist file
        if plist_dest.exists():
            plist_dest.unlink()
            print("Service plist removed")
        
        return True
    except Exception as e:
        print(f"Failed to uninstall service: {e}")
        return False

def check_dependencies():
    """Check if required dependencies are installed"""
    dependencies = {
        "ffmpeg": ["ffmpeg", "-version"],
        "python3": ["python3", "--version"]
    }
    
    missing = []
    for name, cmd in dependencies.items():
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            print(f"✓ {name} is installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"✗ {name} is missing")
            missing.append(name)
    
    if missing:
        print("\nInstall missing dependencies:")
        if "ffmpeg" in missing:
            print("  brew install ffmpeg")
        return False
    
    return True

def create_default_config():
    """Create default configuration file"""
    config = {
        "audio": {
            "chunk_duration": 300,  # 5 minutes
            "sample_rate": 44100,
            "quality": "medium",
            "format": "wav"
        },
        "storage": {
            "temp_path": "/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/MacProAudio",
            "base_path": "/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes"
        },
        "transcription": {
            "engine": "macwhisper",  # or "faster-whisper"
            "language": "auto",
            "model_size": "base"
        }
    }
    
    config_file = Path("config.json")
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Created configuration: {config_file}")
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 setup.py [install|uninstall|check]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "install":
        print("Installing Context Capture System...")
        
        if not check_dependencies():
            print("Please install missing dependencies first")
            sys.exit(1)
        
        create_folder_structure()
        create_default_config()
        
        if install_service():
            print("\n✓ Installation complete!")
            print("Audio capture service is now running.")
            print("Check logs at: ~/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Scripting/logs/")
        else:
            print("Installation failed")
            sys.exit(1)
    
    elif command == "uninstall":
        print("Uninstalling Context Capture System...")
        if uninstall_service():
            print("✓ Uninstallation complete")
        else:
            print("Uninstallation failed")
            sys.exit(1)
    
    elif command == "check":
        print("Checking system status...")
        check_dependencies()
        
        # Check if service is running
        try:
            result = subprocess.run(["launchctl", "list", "com.contextcapture.audio"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✓ Service is loaded")
            else:
                print("✗ Service is not loaded")
        except Exception as e:
            print(f"✗ Could not check service status: {e}")
    
    else:
        print("Unknown command. Use: install, uninstall, or check")
        sys.exit(1)

if __name__ == "__main__":
    main()