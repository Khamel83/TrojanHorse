#!/usr/bin/env python3
"""
TrojanHorse Analysis Router
Unified interface for local/cloud/hybrid analysis routing with backward compatibility.
Priority: Simplicity, reliability, and preserve all existing functionality.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Literal
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AnalysisRouter:
    """Unified analysis interface routing to local or cloud analysis"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self.load_config(config_path)
        self.local_analyzer = None
        self.gemini_processor = None
        
    def load_config(self, config_path: str) -> Dict:
        """Load configuration with sensible defaults"""
        default_config = {
            "analysis": {
                "default_mode": "local",  # local, cloud, or hybrid
                "local_model": "qwen3:8b",
                "cloud_model": "google/gemini-2.0-flash-001",
                "cost_limit_daily": 0.20,
                "enable_pii_detection": True,
                "hybrid_threshold_words": 1000  # Use cloud for longer transcripts
            },
            "prompts": {
                "local_analysis_file": "prompts/local_analysis.txt",
                "gemini_analysis_file": "prompts/gemini_analysis.txt"
            }
        }
        
        if Path(config_path).exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                # Merge with defaults
                if "analysis" not in config:
                    config["analysis"] = default_config["analysis"]
                if "prompts" not in config:
                    config["prompts"] = default_config["prompts"]
                return config
        
        return default_config
    
    def get_local_analyzer(self):
        """Lazy load local analyzer"""
        if self.local_analyzer is None:
            try:
                from analyze_local import LocalAnalyzer
                self.local_analyzer = LocalAnalyzer(
                    model=self.config["analysis"]["local_model"],
                    prompt_file=self.config["prompts"]["local_analysis_file"]
                )
                logger.info("Local analyzer initialized")
            except ImportError as e:
                logger.error(f"Failed to import LocalAnalyzer: {e}")
                # Fallback to simple analyze.py functions
                try:
                    import analyze
                    self.local_analyzer = analyze
                    logger.info("Fallback to simple analyze.py functions")
                except ImportError:
                    logger.error("No local analysis available")
                    self.local_analyzer = None
        return self.local_analyzer
    
    def get_gemini_processor(self):
        """Lazy load Gemini processor"""
        if self.gemini_processor is None:
            try:
                from process_gemini import GeminiProcessor
                self.gemini_processor = GeminiProcessor(
                    model=self.config["analysis"]["cloud_model"],
                    prompt_file=self.config["prompts"]["gemini_analysis_file"],
                    cost_limit_daily=self.config["analysis"]["cost_limit_daily"]
                )
                logger.info("Gemini processor initialized")
            except (ImportError, ValueError) as e:
                logger.warning(f"Gemini processor not available: {e}")
                self.gemini_processor = None
        return self.gemini_processor
    
    def determine_analysis_mode(self, 
                              text: str, 
                              requested_mode: Optional[str] = None) -> Literal["local", "cloud"]:
        """Determine whether to use local or cloud analysis"""
        
        if requested_mode in ["local", "cloud"]:
            return requested_mode
        
        # Use configured default mode
        default_mode = self.config["analysis"]["default_mode"]
        
        if default_mode == "hybrid":
            # Use word count to decide
            word_count = len(text.split())
            threshold = self.config["analysis"]["hybrid_threshold_words"]
            
            if word_count > threshold:
                logger.info(f"Using cloud analysis for long transcript ({word_count} words)")
                return "cloud"
            else:
                logger.info(f"Using local analysis for short transcript ({word_count} words)")
                return "local"
        
        return default_mode if default_mode in ["local", "cloud"] else "local"
    
    def analyze_transcript(self, 
                         transcript_path: Union[str, Path],
                         mode: Optional[str] = None) -> Dict:
        """
        Unified transcript analysis interface
        
        Args:
            transcript_path: Path to transcript file
            mode: 'local', 'cloud', or None for auto-detection
            
        Returns:
            Unified analysis result dictionary
        """
        transcript_path = Path(transcript_path)
        
        if not transcript_path.exists():
            logger.error(f"Transcript file not found: {transcript_path}")
            return {"error": "File not found", "status": "failed"}
        
        try:
            # Read transcript
            if transcript_path.suffix == '.json':
                with open(transcript_path, 'r') as f:
                    transcript_data = json.load(f)
                    text = transcript_data.get('text', transcript_data.get('transcript', ''))
            else:
                text = transcript_path.read_text()
                
            if not text.strip():
                logger.warning(f"Empty transcript: {transcript_path}")
                return {"error": "Empty transcript", "status": "failed"}
            
            # Determine analysis mode
            analysis_mode = self.determine_analysis_mode(text, mode)
            logger.info(f"Analyzing {transcript_path.name} using {analysis_mode} analysis")
            
            # Route to appropriate analyzer
            if analysis_mode == "local":
                result = self.analyze_local(text, transcript_path)
            else:
                result = self.analyze_cloud(text, transcript_path)
            
            # Save result as markdown
            if result.get("status") == "completed":
                self.save_analysis_markdown(result, transcript_path)
            
            return result
                
        except Exception as e:
            logger.error(f"Analysis failed for {transcript_path}: {e}")
            return {"error": str(e), "status": "failed"}
    
    def analyze_local(self, text: str, source_path: Path) -> Dict:
        """Analyze using local models"""
        analyzer = self.get_local_analyzer()
        
        if analyzer is None:
            return {"error": "Local analyzer not available", "status": "failed"}
        
        try:
            # Check if we have the sophisticated LocalAnalyzer
            if hasattr(analyzer, 'process_transcript'):
                # LocalAnalyzer expects a file path, not text directly
                result = analyzer.process_transcript(str(source_path))
                if result and isinstance(result, dict):
                    result["status"] = "completed"
                    result["analysis_mode"] = "local"
                    result["model"] = self.config["analysis"]["local_model"]
                    if "timestamp" not in result:
                        result["timestamp"] = datetime.now().isoformat()
                    return result
                else:
                    return {"error": "Local analyzer returned invalid result", "status": "failed"}
            
            # Fallback to simple analyze.py functions
            elif hasattr(analyzer, 'summarize'):
                summary = analyzer.summarize(text)
                action_items = analyzer.extract_action_items(text) if hasattr(analyzer, 'extract_action_items') else []
                
                return {
                    "status": "completed",
                    "analysis_mode": "local",
                    "model": self.config["analysis"]["local_model"],
                    "source_file": str(source_path),
                    "timestamp": datetime.now().isoformat(),
                    "content_summary": summary,
                    "action_items": action_items,
                    "word_count": len(text.split())
                }
            
            else:
                return {"error": "Invalid local analyzer", "status": "failed"}
                
        except Exception as e:
            logger.error(f"Local analysis failed: {e}")
            return {"error": f"Local analysis failed: {e}", "status": "failed"}
    
    def analyze_cloud(self, text: str, source_path: Path) -> Dict:
        """Analyze using cloud models"""
        processor = self.get_gemini_processor()
        
        if processor is None:
            logger.warning("Cloud processor not available, falling back to local")
            return self.analyze_local(text, source_path)
        
        try:
            result = processor.process_transcript_text(text)
            result["source_file"] = str(source_path)
            result["analysis_mode"] = "cloud"
            result["timestamp"] = datetime.now().isoformat()
            return result
            
        except Exception as e:
            logger.error(f"Cloud analysis failed: {e}, falling back to local")
            return self.analyze_local(text, source_path)
    
    def batch_analyze(self, 
                     transcript_paths: List[Union[str, Path]], 
                     mode: Optional[str] = None) -> List[Dict]:
        """Analyze multiple transcripts"""
        results = []
        
        for path in transcript_paths:
            result = self.analyze_transcript(path, mode)
            results.append(result)
            
            # Small delay to avoid overwhelming APIs
            time.sleep(0.5)
        
        return results
    
    def analyze_directory(self, 
                         directory: Union[str, Path], 
                         pattern: str = "*.txt",
                         mode: Optional[str] = None) -> List[Dict]:
        """Analyze all transcripts in a directory"""
        directory = Path(directory)
        
        if not directory.exists():
            logger.error(f"Directory not found: {directory}")
            return []
        
        transcript_files = list(directory.glob(pattern))
        if not transcript_files:
            logger.warning(f"No transcript files found in {directory} matching {pattern}")
            return []
        
        logger.info(f"Found {len(transcript_files)} transcript files to analyze")
        return self.batch_analyze(transcript_files, mode)
    
    def save_analysis_markdown(self, analysis: Dict, transcript_path: Union[str, Path]) -> bool:
        """Save analysis as markdown file alongside transcript"""
        transcript_path = Path(transcript_path)
        
        try:
            # Save as markdown file alongside transcript
            analysis_file = transcript_path.with_suffix('.analysis.md')
            
            # Create markdown content
            content = f"# Analysis: {transcript_path.name}\n\n"
            content += f"**Generated:** {analysis.get('timestamp', datetime.now().isoformat())}\n"
            content += f"**Mode:** {analysis.get('analysis_mode', 'unknown')}\n"
            content += f"**Model:** {analysis.get('model', 'unknown')}\n\n"
            
            # Add summary if available
            if 'content_summary' in analysis:
                content += f"## Summary\n\n{analysis['content_summary']}\n\n"
            elif 'summary' in analysis:
                content += f"## Summary\n\n{analysis['summary']}\n\n"
            
            # Add action items if available
            if 'action_items' in analysis and analysis['action_items']:
                content += f"## Action Items\n\n"
                for i, item in enumerate(analysis['action_items'], 1):
                    content += f"{i}. {item}\n"
                content += "\n"
            
            # Add key points if available
            if 'key_points' in analysis and analysis['key_points']:
                content += f"## Key Points\n\n"
                for point in analysis['key_points']:
                    content += f"- {point}\n"
                content += "\n"
            
            # Add any additional structured data as sections
            for key, value in analysis.items():
                if key not in ['timestamp', 'analysis_mode', 'model', 'content_summary', 'summary', 'action_items', 'key_points', 'source_file', 'status', 'error']:
                    if isinstance(value, str) and len(value) > 50:
                        content += f"## {key.replace('_', ' ').title()}\n\n{value}\n\n"
                    elif isinstance(value, list):
                        content += f"## {key.replace('_', ' ').title()}\n\n"
                        for item in value:
                            content += f"- {item}\n"
                        content += "\n"
            
            # Write markdown file
            analysis_file.write_text(content)
            logger.info(f"Saved analysis as markdown: {analysis_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")
            return False
    
    def get_analysis_stats(self) -> Dict:
        """Get analysis statistics and capabilities"""
        stats = {
            "local_available": self.get_local_analyzer() is not None,
            "cloud_available": self.get_gemini_processor() is not None,
            "default_mode": self.config["analysis"]["default_mode"],
            "local_model": self.config["analysis"]["local_model"],
            "cloud_model": self.config["analysis"]["cloud_model"]
        }
        
        # Check daily cost limits if Gemini processor available
        if stats["cloud_available"]:
            try:
                processor = self.get_gemini_processor()
                if hasattr(processor, 'check_daily_cost_limit'):
                    stats["cloud_cost_ok"] = processor.check_daily_cost_limit()
                    stats["daily_cost_limit"] = self.config["analysis"]["cost_limit_daily"]
            except:
                pass
        
        return stats

def main():
    """Command line interface"""
    if len(sys.argv) < 2:
        print("Usage: python3 analysis_router.py <transcript_file> [mode]")
        print("  mode: local, cloud, or auto (default)")
        sys.exit(1)
    
    transcript_file = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else None
    
    router = AnalysisRouter()
    
    # Show capabilities
    stats = router.get_analysis_stats()
    print(f"Analysis capabilities: Local={stats['local_available']}, Cloud={stats['cloud_available']}")
    
    # Analyze transcript
    result = router.analyze_transcript(transcript_file, mode)
    
    # Output results (markdown is saved automatically)
    output_file = Path(transcript_file).with_suffix('.analysis.md')
    
    print(f"Analysis complete: {output_file}")
    print(f"Status: {result.get('status', 'unknown')}")
    
    if result.get('status') == 'completed':
        print(f"Mode: {result.get('analysis_mode', 'unknown')}")
        print(f"Model: {result.get('model', 'unknown')}")
        if 'content_summary' in result:
            print(f"Summary: {result['content_summary'][:100]}...")
        elif 'summary' in result:
            print(f"Summary: {result['summary'][:100]}...")

if __name__ == "__main__":
    main()