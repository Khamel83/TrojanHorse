#!/usr/bin/env python3
"""
Hotkey Client for TrojanHorse Context Capture System
"""

import sys
import os
import requests
import pyperclip
from pynput import keyboard
import time
import logging
from config_manager import ConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HotkeyClient:
    def __init__(self, config_path="config.json"):
        self.config_manager = ConfigManager(config_path=config_path)
        self.config = self.config_manager.config
        self.api_port = self.config.get("workflow_integration", {}).get("internal_api_port", 5001)
        self.hotkey_str = self.config.get("workflow_integration", {}).get("hotkey", "<cmd>+<shift>+c")
        self.api_url = f"http://127.0.0.1:{self.api_port}/search"

        # Parse hotkey string for pynput
        self.hotkey = self._parse_hotkey(self.hotkey_str)
        logger.info(f"Hotkey client initialized. Listening for: {self.hotkey_str}")

    def _parse_hotkey(self, hotkey_str: str):
        # pynput expects a specific format for hotkeys
        # Example: '<cmd>+<shift>+c' -> '<cmd>+<shift>+c'
        # This is a basic parser, can be extended for more complex keys
        return hotkey_str.replace("<cmd>", "<cmd>").replace("<shift>", "<shift>").replace("<alt>", "<alt>").replace("<ctrl>", "<ctrl>")

    def on_activate(self):
        logger.info("Hotkey activated!")
        try:
            clipboard_content = pyperclip.paste()
            if not clipboard_content.strip():
                logger.warning("Clipboard is empty, no search performed.")
                self._send_notification("TrojanHorse", "Clipboard is empty.")
                return

            logger.info(f"Searching for: {clipboard_content[:50]}...")
            response = requests.get(self.api_url, params={'query': clipboard_content}, timeout=5)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            
            results = response.json().get("results", [])

            if results:
                top_result = results[0]
                snippet = top_result.get("snippet", "No snippet available.")
                timestamp = top_result.get("timestamp", "")
                notification_message = f"[{timestamp}] {snippet}"
                self._send_notification("TrojanHorse Search Result", notification_message)
                logger.info(f"Displayed notification: {notification_message}")
            else:
                self._send_notification("TrojanHorse", "No relevant results found.")
                logger.info("No relevant results found.")

        except requests.exceptions.ConnectionError:
            logger.error(f"Could not connect to internal API at {self.api_url}. Is it running?")
            self._send_notification("TrojanHorse Error", "Internal API not running.")
        except requests.exceptions.Timeout:
            logger.error("Internal API request timed out.")
            self._send_notification("TrojanHorse Error", "Internal API timed out.")
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            self._send_notification("TrojanHorse Error", f"API request failed: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            self._send_notification("TrojanHorse Error", f"An unexpected error occurred: {e}")

    def _send_notification(self, title: str, message: str):
        # macOS specific notification using osascript
        try:
            subprocess.run(['osascript', '-e', f'display notification "{message}" with title "{title}"'
            ], check=True)
        except Exception as e:
            logger.error(f"Failed to send macOS notification: {e}")

    def start_listening(self):
        logger.info("Starting hotkey listener...")
        with keyboard.GlobalHotKey(self.hotkey, self.on_activate) as h:
            h.join()

if __name__ == "__main__":
    import subprocess
    client = HotkeyClient()
    try:
        client.start_listening()
    except KeyboardInterrupt:
        logger.info("Hotkey client stopped by user.")
    except Exception as e:
        logger.critical(f"Hotkey client crashed: {e}")
        sys.exit(1)
