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
            
            # Trigger analysis (local or cloud based on user choice)
            self.trigger_analysis(transcript_file)
            
        except Exception as e:
            self.logger.error(f"Post-processing failed: {e}")
    
    def trigger_analysis(self, transcript_file):
        """Trigger analysis (local or cloud) based on user choice"""
        # Store current transcript for user prompt
        self.current_transcript = transcript_file
        analysis_type = self.get_analysis_choice()
        
        if analysis_type == "cloud":
            self.trigger_cloud_analysis(transcript_file)
        elif analysis_type == "local":
            self.trigger_local_analysis(transcript_file)
        elif analysis_type == "both":
            self.trigger_local_analysis(transcript_file)
            self.trigger_cloud_analysis(transcript_file)
        else:
            self.logger.info("No analysis selected")
    
    def get_analysis_choice(self):
        """Get user's choice for analysis type"""
        # Check if there's a preference in config
        analysis_config = self.config.get("analysis", {})
        default_type = analysis_config.get("default_type", "prompt")
        
        if default_type == "auto_local":
            return "local"
        elif default_type == "auto_cloud":
            return "cloud"
        elif default_type == "auto_both":
            return "both"
        elif default_type == "none":
            return "none"
        else:
            # Interactive prompt
            try:
                print("\n" + "="*50)
                print(f"📝 Transcript ready: {Path(self.current_transcript).name}")
                print("="*50)
                print("Choose analysis type:")
                print("  1. Local Analysis (Privacy-first, Ollama)")
                print("  2. Cloud Analysis (Advanced, OpenRouter)")
                print("  3. Both Local and Cloud")
                print("  4. No Analysis")
                print("  5. Set Default (auto-mode)")
                
                choice = input("\nEnter choice (1-5): ").strip()
                
                if choice == "1":
                    return "local"
                elif choice == "2":
                    return "cloud"
                elif choice == "3":
                    return "both"
                elif choice == "4":
                    return "none"
                elif choice == "5":
                    return self.set_default_analysis()
                else:
                    print("Invalid choice, defaulting to local analysis")
                    return "local"
                    
            except (KeyboardInterrupt, EOFError):
                print("\nDefaulting to local analysis")
                return "local"
    
    def set_default_analysis(self):
        """Set default analysis preference"""
        try:
            print("\nSet default analysis mode:")
            print("  1. Auto Local (always use local)")
            print("  2. Auto Cloud (always use cloud)")
            print("  3. Auto Both (always use both)")
            print("  4. Always Prompt (current behavior)")
            print("  5. None (disable analysis)")
            
            choice = input("Enter choice (1-5): ").strip()
            
            mode_map = {
                "1": "auto_local",
                "2": "auto_cloud", 
                "3": "auto_both",
                "4": "prompt",
                "5": "none"
            }
            
            if choice in mode_map:
                new_mode = mode_map[choice]
                self.update_config_analysis_default(new_mode)
                print(f"✅ Default analysis set to: {new_mode}")
                
                # Return the choice for this session
                if choice == "1":
                    return "local"
                elif choice == "2":
                    return "cloud"
                elif choice == "3":
                    return "both"
                else:
                    return "none"
            else:
                print("Invalid choice, using local analysis")
                return "local"
                
        except (KeyboardInterrupt, EOFError):
            print("\nUsing local analysis")
            return "local"
    
    def update_config_analysis_default(self, default_type):
        """Update config file with new default analysis type"""
        try:
            # Update in-memory config
            if "analysis" not in self.config:
                self.config["analysis"] = {}
            self.config["analysis"]["default_type"] = default_type
            
            # Write back to config file
            config_path = Path(__file__).parent / "config.json"
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
                
            self.logger.info(f"Updated default analysis to: {default_type}")
            
        except Exception as e:
            self.logger.error(f"Failed to update config: {e}")
    
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
                print("✅ Local analysis completed")
            else:
                self.logger.warning(f"Local analysis failed for: {transcript_file}")
                print("⚠️  Local analysis failed")
                
        except ImportError as e:
            self.logger.info(f"Local analysis not available: {e}")
            print(f"⚠️  Local analysis not available: {e}")
        except Exception as e:
            self.logger.error(f"Local analysis error: {e}")
            print(f"❌ Local analysis error: {e}")
    
    def trigger_cloud_analysis(self, transcript_file):
        """Trigger cloud analysis using cloud_analyze.py"""
        try:
            # Import cloud analysis module
            import sys
            from pathlib import Path
            
            # Add current directory to path to import cloud_analyze
            current_dir = Path(__file__).parent
            if str(current_dir) not in sys.path:
                sys.path.insert(0, str(current_dir))
            
            # Import relative to TrojanHorse directory
            parent_dir = current_dir.parent
            if str(parent_dir) not in sys.path:
                sys.path.insert(0, str(parent_dir))
            
            from cloud_analyze import analyze
            
            # Read transcript content
            transcript_content = transcript_file.read_text()
            
            # Define analysis prompts
            prompts = [
                ("summary", "Provide a concise summary of the key points discussed in this transcript."),
                ("action_items", "Extract any action items, tasks, or follow-ups mentioned in this transcript."),
                ("insights", "Identify any insights, decisions, or important conclusions from this transcript.")
            ]
            
            analysis_results = []
            
            print("🤖 Running cloud analysis...")
            
            for prompt_name, prompt_text in prompts:
                try:
                    result = analyze(transcript_content, prompt_text)
                    analysis_results.append(f"## {prompt_name.title()}\n\n{result}\n")
                    print(f"✅ {prompt_name.title()} completed")
                except Exception as e:
                    error_msg = f"❌ {prompt_name.title()} failed: {e}"
                    print(error_msg)
                    self.logger.error(error_msg)
                    analysis_results.append(f"## {prompt_name.title()}\n\nAnalysis failed: {e}\n")
            
            # Save cloud analysis to daily notes
            if analysis_results:
                self.save_cloud_analysis(transcript_file, analysis_results)
                self.logger.info(f"Cloud analysis completed for: {transcript_file}")
                print("✅ Cloud analysis completed and saved")
            else:
                self.logger.warning(f"No cloud analysis results for: {transcript_file}")
                print("⚠️  No cloud analysis results")
                
        except ImportError as e:
            self.logger.error(f"Cloud analysis not available: {e}")
            print(f"❌ Cloud analysis not available: {e}")
        except Exception as e:
            self.logger.error(f"Cloud analysis error: {e}")
            print(f"❌ Cloud analysis error: {e}")
    
    def save_cloud_analysis(self, transcript_file, analysis_results):
        """Save cloud analysis results to daily notes file"""
        try:
            # Create analysis filename
            analysis_file = transcript_file.with_name(f"{transcript_file.stem}_cloud_analysis.md")
            
            # Create analysis content
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content = f"# Cloud Analysis\n\n"
            content += f"**Transcript:** {transcript_file.name}\n"
            content += f"**Generated:** {timestamp}\n"
            content += f"**Engine:** OpenRouter + Gemini Flash 2.0\n\n"
            content += "---\n\n"
            
            # Add all analysis results
            for result in analysis_results:
                content += result + "\n"
            
            # Write analysis file
            analysis_file.write_text(content)
            
            # Also append to daily summary file
            self.append_to_daily_summary(transcript_file, analysis_results)
            
            self.logger.info(f"Cloud analysis saved to: {analysis_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save cloud analysis: {e}")
            raise
    
    def append_to_daily_summary(self, transcript_file, analysis_results):
        """Append analysis to daily summary file"""
        try:
            # Get daily summary file
            daily_summary_file = transcript_file.parent / "daily_summary.md"
            
            # Create header for this transcript
            timestamp = datetime.now().strftime("%H:%M:%S")
            entry_header = f"\n## {transcript_file.stem} ({timestamp})\n\n"
            
            # Combine analysis results
            entry_content = ""
            for result in analysis_results:
                entry_content += result + "\n"
            
            # Append to daily summary
            if daily_summary_file.exists():
                existing_content = daily_summary_file.read_text()
                new_content = existing_content + entry_header + entry_content
            else:
                today = datetime.now().strftime("%Y-%m-%d")
                header = f"# Daily Summary - {today}\n\n"
                new_content = header + entry_header + entry_content
            
            daily_summary_file.write_text(new_content)
            self.logger.info(f"Added to daily summary: {daily_summary_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to update daily summary: {e}")
    
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