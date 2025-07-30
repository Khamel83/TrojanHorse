#!/usr/bin/env python3
"""
Transcription Module for Context Capture System
Handles audio transcription using MacWhisper or faster-whisper
"""

import os
import sys
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime

class AudioTranscriber:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.setup_logging()
    
    def load_config(self, config_path):
        """Load configuration"""
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            # Default config
            return {
                "transcription": {
                    "engine": "macwhisper",
                    "language": "auto",
                    "model_size": "base"
                }
            }
    
    def setup_logging(self):
        """Setup logging to daily folder"""
        today = datetime.now().strftime("%Y-%m-%d")
        base_path = Path(self.config.get("storage", {}).get("base_path", 
                        "/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes"))
        log_dir = base_path / today
        log_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "transcription.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def transcribe_with_macwhisper(self, audio_file):
        """Transcribe using MacWhisper CLI"""
        try:
            # Check if MacWhisper CLI is available
            subprocess.run(["macwhisper", "--version"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            output_file = audio_file.with_suffix('.txt')
            
            cmd = [
                "macwhisper",
                "--model", self.config["transcription"]["model_size"],
                "--language", self.config["transcription"]["language"],
                "--output-format", "txt",
                "--output", str(output_file),
                str(audio_file)
            ]
            
            self.logger.info(f"Starting MacWhisper transcription: {audio_file}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info(f"MacWhisper transcription completed: {output_file}")
                return output_file
            else:
                self.logger.error(f"MacWhisper failed: {result.stderr}")
                return None
                
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.warning("MacWhisper not available, falling back to faster-whisper")
            return None
    
    def transcribe_with_faster_whisper(self, audio_file):
        """Transcribe using faster-whisper (fallback)"""
        try:
            # Try to import faster-whisper
            from faster_whisper import WhisperModel
            
            output_file = audio_file.with_suffix('.txt')
            
            self.logger.info(f"Starting faster-whisper transcription: {audio_file}")
            
            # Initialize model (downloads first time)
            model = WhisperModel(self.config["transcription"]["model_size"])
            
            # Transcribe
            segments, info = model.transcribe(str(audio_file), 
                                            language=self.config["transcription"]["language"] if self.config["transcription"]["language"] != "auto" else None)
            
            # Write transcript
            with open(output_file, 'w') as f:
                f.write(f"Transcription of {audio_file.name}\n")
                f.write(f"Language: {info.language} (confidence: {info.language_probability:.2f})\n")
                f.write(f"Duration: {info.duration:.2f}s\n")
                f.write("-" * 50 + "\n\n")
                
                for segment in segments:
                    timestamp = f"[{segment.start:.2f}s -> {segment.end:.2f}s]"
                    f.write(f"{timestamp} {segment.text}\n")
            
            self.logger.info(f"faster-whisper transcription completed: {output_file}")
            return output_file
            
        except ImportError:
            self.logger.error("faster-whisper not installed. Install with: pip install faster-whisper")
            return None
        except Exception as e:
            self.logger.error(f"faster-whisper transcription failed: {e}")
            return None
    
    def transcribe_with_system_whisper(self, audio_file):
        """Transcribe using system whisper command (last resort)"""
        try:
            # Check if whisper command is available
            subprocess.run(["whisper", "--help"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            output_file = audio_file.with_suffix('.txt')
            
            cmd = [
                "whisper",
                str(audio_file),
                "--model", self.config["transcription"]["model_size"],
                "--output_format", "txt",
                "--output_dir", str(audio_file.parent)
            ]
            
            if self.config["transcription"]["language"] != "auto":
                cmd.extend(["--language", self.config["transcription"]["language"]])
            
            self.logger.info(f"Starting system whisper transcription: {audio_file}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Whisper creates filename.txt, we need to find it
                expected_file = audio_file.parent / f"{audio_file.stem}.txt"
                if expected_file.exists():
                    if expected_file != output_file:
                        expected_file.rename(output_file)
                    self.logger.info(f"System whisper transcription completed: {output_file}")
                    return output_file
            
            self.logger.error(f"System whisper failed: {result.stderr}")
            return None
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.error("System whisper not available")
            return None
    
    def transcribe_file(self, audio_file):
        """Transcribe audio file using best available method"""
        audio_file = Path(audio_file)
        
        if not audio_file.exists():
            self.logger.error(f"Audio file not found: {audio_file}")
            return None
        
        self.logger.info(f"Transcribing: {audio_file}")
        
        # Try transcription methods in order of preference
        methods = [
            ("MacWhisper", self.transcribe_with_macwhisper),
            ("faster-whisper", self.transcribe_with_faster_whisper),
            ("system whisper", self.transcribe_with_system_whisper)
        ]
        
        for method_name, method in methods:
            try:
                result = method(audio_file)
                if result:
                    self.post_process_transcript(result)
                    
                    # Delete original audio file after successful transcription
                    if self.config.get("storage", {}).get("auto_delete_audio", True):
                        try:
                            audio_file.unlink()
                            self.logger.info(f"Deleted audio file: {audio_file}")
                        except Exception as e:
                            self.logger.warning(f"Could not delete audio file: {e}")
                    
                    return result
            except Exception as e:
                self.logger.error(f"{method_name} failed: {e}")
                continue
        
        self.logger.error("All transcription methods failed")
        return None
    
    def post_process_transcript(self, transcript_file):
        """Post-process transcript (clean up, add metadata)"""
        try:
            transcript_file = Path(transcript_file)
            
            # Read current content
            content = transcript_file.read_text()
            
            # Add metadata header if not present
            if not content.startswith("Transcription of"):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                header = f"Transcription of {transcript_file.stem}\n"
                header += f"Generated: {timestamp}\n"
                header += f"Engine: {self.config['transcription']['engine']}\n"
                header += "-" * 50 + "\n\n"
                
                content = header + content
                transcript_file.write_text(content)
            
            self.logger.info(f"Post-processed transcript: {transcript_file}")
            
            # Trigger local analysis if available
            self.trigger_local_analysis(transcript_file)
            
        except Exception as e:
            self.logger.error(f"Post-processing failed: {e}")
    
    def trigger_local_analysis(self, transcript_file):
        """Trigger local analysis using analyze_local.py"""
        try:
            # Import LocalAnalyzer from analyze_local module
            import sys
            from pathlib import Path
            
            # Add current directory to path to import analyze_local
            current_dir = Path(__file__).parent
            if str(current_dir) not in sys.path:
                sys.path.insert(0, str(current_dir))
            
            from analyze_local import LocalAnalyzer
            
            # Initialize analyzer and process transcript
            analyzer = LocalAnalyzer()
            analysis = analyzer.process_transcript(transcript_file)
            
            if analysis and analyzer.save_analysis(analysis):
                self.logger.info(f"Local analysis completed for: {transcript_file}")
            else:
                self.logger.warning(f"Local analysis failed for: {transcript_file}")
                
        except ImportError as e:
            self.logger.info(f"Local analysis not available: {e}")
        except Exception as e:
            self.logger.error(f"Local analysis error: {e}")
    
    def process_pending_files(self):
        """Process all pending audio files in temp directory"""
        temp_path = Path(self.config.get("storage", {}).get("temp_path", 
                        "/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/MacProAudio"))
        
        if not temp_path.exists():
            self.logger.info("No temp directory found")
            return
        
        # Find all audio files
        audio_files = list(temp_path.glob("*.wav")) + list(temp_path.glob("*.mp3")) + list(temp_path.glob("*.m4a"))
        
        if not audio_files:
            self.logger.info("No pending audio files found")
            return
        
        self.logger.info(f"Found {len(audio_files)} pending audio files")
        
        for audio_file in audio_files:
            try:
                self.transcribe_file(audio_file)
            except Exception as e:
                self.logger.error(f"Failed to process {audio_file}: {e}")

def main():
    transcriber = AudioTranscriber()
    
    if len(sys.argv) > 1:
        # Transcribe specific file
        audio_file = sys.argv[1]
        result = transcriber.transcribe_file(audio_file)
        if result:
            print(f"Transcription completed: {result}")
        else:
            print("Transcription failed")
            sys.exit(1)
    else:
        # Process all pending files
        transcriber.process_pending_files()

if __name__ == "__main__":
    main()