#!/usr/bin/env python3
"""
Setup script for TrojanHorse Context Capture System
Creates folder structure, installs dependencies, and sets up the main service.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
import shutil

# Define project root (assuming setup.py is in the root)
PROJECT_ROOT = Path(__file__).parent

def create_folder_structure():
    """Create the necessary folder structure based on default config paths."""
    # Load a temporary config manager to get default paths
    # This avoids circular imports with config_manager.py
    temp_config_path = PROJECT_ROOT / "config.template.json"
    
    try:
        with open(temp_config_path, 'r') as f:
            config_defaults = json.load(f)
    except FileNotFoundError:
        print(f"Error: config.template.json not found at {temp_config_path}")
        return False
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in config.template.json at {temp_config_path}")
        return False

    storage_config = config_defaults.get("storage", {})
    base_path = Path(os.path.expanduser(storage_config.get("base_path", "~/Meeting Notes")))
    temp_path = Path(os.path.expanduser(storage_config.get("temp_path", "~/TrojanHorse/temp")))
    logs_path = PROJECT_ROOT / "logs" # Logs are always relative to project root
    
    # Create directories
    for path in [base_path, temp_path, logs_path]:
        try:
            path.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {path}")
        except Exception as e:
            print(f"Error creating directory {path}: {e}")
            return False
    
    return True

def install_service():
    """Install the health_monitor.py as a launchd service."""
    plist_source = PROJECT_ROOT / "com.contextcapture.audio.plist"
    plist_dest = Path.home() / "Library/LaunchAgents/com.contextcapture.audio.plist"
    
    # Ensure the plist file exists and is correctly configured
    if not plist_source.exists():
        print(f"Error: Service plist file not found at {plist_source}")
        print("Please ensure 'com.contextcapture.audio.plist' is in the project root.")
        return False

    # Read plist content and replace placeholders if any (though it should point to health_monitor directly)
    plist_content = plist_source.read_text()
    # Ensure the plist points to the health_monitor.py script with the 'monitor' command
    # This assumes the plist is designed to be generic and just needs the path to the project
    # For example, ProgramArguments might be:
    # <array>
    #   <string>/usr/bin/python3</string>
    #   <string>/path/to/TrojanHorse/src/health_monitor.py</string>
    #   <string>monitor</string>
    # </array>
    # <key>WorkingDirectory</key>
    # <string>/path/to/TrojanHorse</string>
    
    # It's safer to instruct the user to manually verify/edit the plist for absolute paths
    # or provide a more sophisticated plist generation here.
    # For now, we assume the provided plist is correctly templated or manually adjusted.

    try:
        # Copy plist file
        plist_dest.parent.mkdir(exist_ok=True)
        plist_dest.write_text(plist_content)
        print(f"Installed service plist: {plist_dest}")
        
        # Load the service
        subprocess.run(["launchctl", "load", str(plist_dest)], check=True)
        print("Service loaded successfully. It will start health_monitor.py.")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to load service with launchctl: {e}")
        print("Please check permissions and ensure the plist file is correctly configured.")
        return False
    except Exception as e:
        print(f"Failed to install service: {e}")
        return False

def uninstall_service():
    """Uninstall the launchd service."""
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
    """Check if required system and Python dependencies are installed."""
    print("Checking system dependencies...")
    system_deps = {
        "ffmpeg": ["ffmpeg", "-version"],
        "python3": ["python3", "--version"],
        "brew": ["brew", "--version"]
    }
    
    missing_system_deps = []
    for name, cmd in system_deps.items():
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            print(f"✓ {name} is installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"✗ {name} is missing")
            missing_system_deps.append(name)
    
    if missing_system_deps:
        print("\n--- Missing System Dependencies ---")
        print("Please install them manually:")
        if "brew" in missing_system_deps:
            print('  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"')
        if "ffmpeg" in missing_system_deps:
            print("  brew install ffmpeg")
        print("-----------------------------------")
        return False

    print("\nChecking Python dependencies...")
    try:
        # Install/update pip dependencies from requirements.txt
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", PROJECT_ROOT / "requirements.txt"], check=True)
        print("✓ Python dependencies installed/updated.")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install Python dependencies: {e}")
        print("Please ensure pip is installed and accessible.")
        return False

    print("\nChecking spaCy language model...")
    try:
        # Check if en_core_web_sm is downloaded
        import spacy
        if not spacy.util.is_package("en_core_web_sm"):
            print("✗ spaCy 'en_core_web_sm' model not found. Attempting to download...")
            subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True)
            print("✓ spaCy 'en_core_web_sm' model downloaded.")
        else:
            print("✓ spaCy 'en_core_web_sm' model is installed.")
    except ImportError:
        print("✗ spaCy library not installed. It should have been installed via requirements.txt.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to download spaCy model: {e}")
        print("Please check your internet connection or try 'python3 -m spacy download en_core_web_sm' manually.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during spaCy check: {e}")
        return False

    return True

def create_default_config():
    """Create default configuration file if it doesn't exist, based on config.template.json."""
    config_file = PROJECT_ROOT / "config.json"
    template_file = PROJECT_ROOT / "config.template.json"

    if config_file.exists():
        print(f"Configuration file already exists: {config_file}. Skipping creation.")
        return True

    if not template_file.exists():
        print(f"Error: config.template.json not found at {template_file}. Cannot create default config.")
        return False

    try:
        shutil.copy(template_file, config_file)
        print(f"Created default configuration: {config_file}")
        print("Please review and edit 'config.json' to customize your settings.")
        return True
    except Exception as e:
        print(f"Error creating default config file: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 setup.py [install|uninstall|check]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "install":
        print("Installing TrojanHorse Context Capture System...")
        
        if not check_dependencies():
            print("\nInstallation aborted due to missing dependencies.")
            sys.exit(1)
        
        if not create_folder_structure():
            print("\nInstallation aborted due to folder creation issues.")
            sys.exit(1)

        if not create_default_config():
            print("\nInstallation aborted due to config file issues.")
            sys.exit(1)
        
        if install_service():
            print("\n✓ Installation complete!")
            print("The main health_monitor.py service is now loaded and should be running.")
            print("You can check its status with: python3 src/health_monitor.py status")
            print("Remember to grant microphone and full disk access permissions in macOS System Settings.")
        else:
            print("\nInstallation failed.")
            sys.exit(1)
    
    elif command == "uninstall":
        print("Uninstalling TrojanHorse Context Capture System...")
        if uninstall_service():
            print("✓ Uninstallation complete.")
        else:
            print("Uninstallation failed.")
            sys.exit(1)
    
    elif command == "check":
        print("Checking system status and dependencies...")
        check_dependencies()
        # Additional checks can be added here, e.g., health_monitor.py status
        print("\nFor a full system health report, run: python3 src/health_monitor.py status")
    
    else:
        print("Unknown command. Use: install, uninstall, or check")
        sys.exit(1)

if __name__ == "__main__":
    main()
