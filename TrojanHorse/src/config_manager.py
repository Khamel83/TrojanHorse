#!/usr/bin/env python3
"""
Configuration Manager for TrojanHorse Context Capture System
Provides easy management of system configuration settings.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConfigManager:
    """Configuration management for TrojanHorse system"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """Load configuration with defaults"""
        default_config = {
            "audio": {
                "chunk_duration": 300,
                "sample_rate": 44100,
                "quality": "medium",
                "format": "wav"
            },
            "storage": {
                "temp_path": "./temp",
                "base_path": "./notes",
                "auto_delete_audio": True
            },
            "transcription": {
                "engine": "macwhisper",
                "language": "auto",
                "model_size": "base"
            },
            "analysis": {
                "default_mode": "local",
                "local_model": "qwen3:8b",
                "cloud_model": "google/gemini-2.0-flash-001",
                "cost_limit_daily": 0.20,
                "enable_pii_detection": True,
                "hybrid_threshold_words": 1000
            },
            "prompts": {
                "local_analysis_file": "prompts/local_analysis.txt",
                "gemini_analysis_file": "prompts/gemini_analysis.txt"
            }
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                # Merge with defaults to ensure all keys exist
                merged = self._deep_merge(default_config, config)
                return merged
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                return default_config
        else:
            return default_config
    
    def _deep_merge(self, base: Dict, overlay: Dict) -> Dict:
        """Deep merge two dictionaries, overlay takes precedence"""
        result = base.copy()
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def save_config(self) -> bool:
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Configuration saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False
    
    def get_value(self, key_path: str) -> Any:
        """Get configuration value using dotted key path (e.g., 'analysis.default_mode')"""
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return None
    
    def set_value(self, key_path: str, value: Any) -> bool:
        """Set configuration value using dotted key path"""
        keys = key_path.split('.')
        config = self.config
        
        try:
            # Navigate to the parent of the target key
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]
            
            # Set the value
            config[keys[-1]] = value
            logger.info(f"Set {key_path} = {value}")
            return True
        except Exception as e:
            logger.error(f"Error setting {key_path}: {e}")
            return False
    
    def show_config(self, section: Optional[str] = None) -> None:
        """Display current configuration"""
        if section:
            if section in self.config:
                print(f"[{section}]")
                self._print_dict(self.config[section], indent=2)
            else:
                print(f"Configuration section '{section}' not found")
        else:
            print("Current Configuration:")
            self._print_dict(self.config)
    
    def _print_dict(self, d: Dict, indent: int = 0) -> None:
        """Pretty print dictionary with indentation"""
        for key, value in d.items():
            if isinstance(value, dict):
                print(" " * indent + f"{key}:")
                self._print_dict(value, indent + 2)
            else:
                print(" " * indent + f"{key}: {value}")
    
    def reset_section(self, section: str) -> bool:
        """Reset a configuration section to defaults"""
        default_config = ConfigManager()._load_config()
        
        if section in default_config:
            self.config[section] = default_config[section].copy()
            logger.info(f"Reset section '{section}' to defaults")
            return True
        else:
            logger.error(f"Section '{section}' not found in defaults")
            return False
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Check required sections
        required_sections = ["audio", "storage", "transcription", "analysis", "prompts"]
        for section in required_sections:
            if section not in self.config:
                issues.append(f"Missing required section: {section}")
        
        # Validate paths exist (if specified as absolute paths)
        for path_key in ["storage.temp_path", "storage.base_path"]:
            path_value = self.get_value(path_key)
            if path_value and Path(path_value).is_absolute():
                if not Path(path_value).exists():
                    issues.append(f"Path does not exist: {path_key} = {path_value}")
        
        # Validate prompt files exist
        for prompt_key in ["prompts.local_analysis_file", "prompts.gemini_analysis_file"]:
            prompt_file = self.get_value(prompt_key)
            if prompt_file and not Path(prompt_file).exists():
                issues.append(f"Prompt file not found: {prompt_key} = {prompt_file}")
        
        # Validate numeric ranges
        chunk_duration = self.get_value("audio.chunk_duration")
        if chunk_duration and (chunk_duration < 30 or chunk_duration > 3600):
            issues.append(f"Audio chunk duration should be 30-3600 seconds: {chunk_duration}")
        
        cost_limit = self.get_value("analysis.cost_limit_daily")
        if cost_limit and (cost_limit < 0 or cost_limit > 10):
            issues.append(f"Daily cost limit should be 0-10 USD: {cost_limit}")
        
        return issues
    
    def interactive_setup(self) -> None:
        """Interactive configuration setup"""
        print("🔧 TrojanHorse Configuration Setup")
        print("=" * 40)
        
        try:
            # Analysis preferences
            print("\n📊 Analysis Preferences:")
            current_mode = self.get_value("analysis.default_mode")
            print(f"Current default mode: {current_mode}")
            
            modes = ["local", "cloud", "hybrid", "prompt"]
            print("Available modes:")
            for i, mode in enumerate(modes, 1):
                print(f"  {i}. {mode}")
            
            choice = input(f"Select mode (1-{len(modes)}, Enter to keep current): ").strip()
            if choice and choice.isdigit() and 1 <= int(choice) <= len(modes):
                new_mode = modes[int(choice) - 1]
                self.set_value("analysis.default_mode", new_mode)
            
            # Local model
            print(f"\n🏠 Local Analysis Model:")
            current_model = self.get_value("analysis.local_model")
            print(f"Current model: {current_model}")
            new_model = input("Enter local model name (Enter to keep current): ").strip()
            if new_model:
                self.set_value("analysis.local_model", new_model)
            
            # Cloud model
            print(f"\n☁️  Cloud Analysis Model:")
            current_cloud = self.get_value("analysis.cloud_model")
            print(f"Current model: {current_cloud}")
            new_cloud = input("Enter cloud model name (Enter to keep current): ").strip()
            if new_cloud:
                self.set_value("analysis.cloud_model", new_cloud)
            
            # Cost limit
            print(f"\n💰 Daily Cost Limit:")
            current_limit = self.get_value("analysis.cost_limit_daily")
            print(f"Current limit: ${current_limit}")
            new_limit = input("Enter daily cost limit in USD (Enter to keep current): ").strip()
            if new_limit:
                try:
                    self.set_value("analysis.cost_limit_daily", float(new_limit))
                except ValueError:
                    print("Invalid number, keeping current value")
            
            # Storage paths
            print(f"\n📁 Storage Paths:")
            current_base = self.get_value("storage.base_path")
            print(f"Current notes path: {current_base}")
            new_base = input("Enter notes directory path (Enter to keep current): ").strip()
            if new_base:
                self.set_value("storage.base_path", new_base)
            
            # Save configuration
            print(f"\n💾 Save Configuration:")
            save = input("Save changes? (Y/n): ").strip().lower()
            if save != 'n':
                if self.save_config():
                    print("✅ Configuration saved successfully!")
                else:
                    print("❌ Failed to save configuration")
            else:
                print("Changes not saved")
                
        except (KeyboardInterrupt, EOFError):
            print("\n\nConfiguration setup cancelled")

def main():
    """Command line interface"""
    parser = argparse.ArgumentParser(description="Manage TrojanHorse configuration")
    parser.add_argument("--config", "-c", default="config.json",
                       help="Configuration file path")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Show configuration
    show_parser = subparsers.add_parser("show", help="Show configuration")
    show_parser.add_argument("section", nargs="?", help="Specific section to show")
    
    # Set configuration value
    set_parser = subparsers.add_parser("set", help="Set configuration value")
    set_parser.add_argument("key", help="Configuration key (dotted path)")
    set_parser.add_argument("value", help="Value to set")
    
    # Get configuration value
    get_parser = subparsers.add_parser("get", help="Get configuration value")
    get_parser.add_argument("key", help="Configuration key (dotted path)")
    
    # Reset section
    reset_parser = subparsers.add_parser("reset", help="Reset section to defaults")
    reset_parser.add_argument("section", help="Section to reset")
    
    # Validate configuration
    subparsers.add_parser("validate", help="Validate configuration")
    
    # Interactive setup
    subparsers.add_parser("setup", help="Interactive configuration setup")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    config_manager = ConfigManager(args.config)
    
    if args.command == "show":
        config_manager.show_config(args.section)
    
    elif args.command == "set":
        # Try to parse value as JSON, fallback to string
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value
        
        if config_manager.set_value(args.key, value):
            config_manager.save_config()
        
    elif args.command == "get":
        value = config_manager.get_value(args.key)
        if value is not None:
            print(value)
        else:
            print(f"Key '{args.key}' not found")
            sys.exit(1)
    
    elif args.command == "reset":
        if config_manager.reset_section(args.section):
            config_manager.save_config()
    
    elif args.command == "validate":
        issues = config_manager.validate_config()
        if issues:
            print("Configuration Issues:")
            for issue in issues:
                print(f"  ❌ {issue}")
            sys.exit(1)
        else:
            print("✅ Configuration is valid")
    
    elif args.command == "setup":
        config_manager.interactive_setup()

if __name__ == "__main__":
    main()