#!/usr/bin/env python3
"""
Main Orchestrator for the TrojanHorse Context Capture System
"""

import sys
import subprocess
from pathlib import Path
from config_manager import ConfigManager

def main():
    """Main function to orchestrate transcription and analysis."""
    try:
        config_manager = ConfigManager()
        config_manager.validate_config()
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    # 1. Run the transcription process
    transcribe_process = subprocess.run(
        [sys.executable, "src/transcribe.py"],
        capture_output=True,
        text=True,
        check=False
    )

    if transcribe_process.returncode != 0:
        print(f"Transcription failed with error:\n{transcribe_process.stderr}")
        sys.exit(1)

    # The output of transcribe.py is a list of file paths
    transcript_paths = transcribe_process.stdout.strip().split('\n')

    if not transcript_paths or not transcript_paths[0]:
        print("No new transcripts to analyze.")
        sys.exit(0)

    # 2. Run the analysis process for each new transcript
    for transcript_path_str in transcript_paths:
        transcript_path = Path(transcript_path_str)
        if transcript_path.exists():
            print(f"Analyzing: {transcript_path.name}")
            analysis_process = subprocess.run(
                [sys.executable, "src/analysis_router.py", str(transcript_path)],
                capture_output=True,
                text=True,
                check=False
            )
            if analysis_process.returncode != 0:
                print(f"Analysis failed for {transcript_path.name}:\n{analysis_process.stderr}")
            else:
                print(analysis_process.stdout)

if __name__ == "__main__":
    main()
