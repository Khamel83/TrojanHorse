#!/usr/bin/env python3
"""
Batch Analysis Tool for TrojanHorse Context Capture System
Processes existing transcripts that don't have analysis files yet.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional
import logging

from analysis_router import AnalysisRouter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BatchAnalyzer:
    """Batch analysis for existing transcripts"""
    
    def __init__(self, config_path: str = "config.json"):
        self.router = AnalysisRouter(config_path)
        self.config = self._load_config(config_path)
        
    def _load_config(self, config_path: str) -> dict:
        """Load configuration"""
        if Path(config_path).exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def find_unanalyzed_transcripts(self, directory: Path) -> List[Path]:
        """Find transcript files that don't have corresponding analysis files"""
        transcript_patterns = ["*.txt", "*.json"]
        unanalyzed = []
        
        for pattern in transcript_patterns:
            for transcript_file in directory.rglob(pattern):
                # Skip files that are clearly not transcripts
                if any(skip in transcript_file.name.lower() for skip in 
                      ['log', 'config', 'readme', 'analysis', 'summary']):
                    continue
                
                # Check if analysis file exists
                analysis_file = transcript_file.with_suffix('.analysis.md')
                if not analysis_file.exists():
                    unanalyzed.append(transcript_file)
                    
        return sorted(unanalyzed)
    
    def analyze_directory(self, 
                         directory: str, 
                         mode: Optional[str] = None,
                         recursive: bool = True,
                         dry_run: bool = False) -> None:
        """Batch analyze all unanalyzed transcripts in a directory"""
        directory_path = Path(directory)
        
        if not directory_path.exists():
            logger.error(f"Directory not found: {directory}")
            return
        
        # Find unanalyzed transcripts
        if recursive:
            unanalyzed = self.find_unanalyzed_transcripts(directory_path)
        else:
            unanalyzed = []
            for pattern in ["*.txt", "*.json"]:
                unanalyzed.extend(directory_path.glob(pattern))
            
            # Filter out already analyzed and non-transcript files
            filtered = []
            for file in unanalyzed:
                if any(skip in file.name.lower() for skip in 
                      ['log', 'config', 'readme', 'analysis', 'summary']):
                    continue
                analysis_file = file.with_suffix('.analysis.md')
                if not analysis_file.exists():
                    filtered.append(file)
            unanalyzed = sorted(filtered)
        
        if not unanalyzed:
            logger.info(f"No unanalyzed transcripts found in {directory}")
            return
        
        logger.info(f"Found {len(unanalyzed)} unanalyzed transcripts")
        
        if dry_run:
            print("DRY RUN - Would analyze the following files:")
            for file in unanalyzed:
                print(f"  {file}")
            return
        
        # Get analysis capabilities
        stats = self.router.get_analysis_stats()
        print(f"Analysis capabilities: Local={stats['local_available']}, Cloud={stats['cloud_available']}")
        
        # Determine analysis mode
        if mode is None:
            mode = self._prompt_for_mode(stats)
        
        if mode == "none":
            logger.info("Analysis cancelled by user")
            return
        
        # Process each file
        success_count = 0
        failure_count = 0
        
        for i, transcript_file in enumerate(unanalyzed, 1):
            print(f"\n[{i}/{len(unanalyzed)}] Processing: {transcript_file.name}")
            
            try:
                result = self.router.analyze_transcript(transcript_file, mode)
                
                if result.get("status") == "completed":
                    success_count += 1
                    logger.info(f"✅ Analysis completed: {transcript_file.name}")
                    
                    # Show brief summary
                    if 'content_summary' in result:
                        print(f"📋 Summary: {result['content_summary'][:80]}...")
                    elif 'summary' in result:
                        print(f"📋 Summary: {result['summary'][:80]}...")
                else:
                    failure_count += 1
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"❌ Analysis failed: {transcript_file.name} - {error_msg}")
                    
            except Exception as e:
                failure_count += 1
                logger.error(f"❌ Exception analyzing {transcript_file.name}: {e}")
        
        # Summary
        print(f"\n📊 Batch Analysis Complete:")
        print(f"  ✅ Successful: {success_count}")
        print(f"  ❌ Failed: {failure_count}")
        print(f"  📁 Total processed: {len(unanalyzed)}")
    
    def _prompt_for_mode(self, stats: dict) -> str:
        """Prompt user for analysis mode"""
        try:
            print("\nBatch Analysis Mode Selection:")
            print("Analysis capabilities:")
            print(f"  🏠 Local:  {'✅ Available' if stats['local_available'] else '❌ Not available'} ({stats.get('local_model', 'unknown')})")
            print(f"  ☁️  Cloud:  {'✅ Available' if stats['cloud_available'] else '❌ Not available'} ({stats.get('cloud_model', 'unknown')})")
            print()
            
            choices = []
            choice_map = {}
            
            if stats["local_available"]:
                choices.append("1. Local Analysis (Privacy-first, offline)")
                choice_map["1"] = "local"
            
            if stats["cloud_available"]:
                choices.append("2. Cloud Analysis (Advanced features)")
                choice_map["2"] = "cloud"
            
            if stats["local_available"] and stats["cloud_available"]:
                choices.append("3. Auto (hybrid local/cloud based on content)")
                choice_map["3"] = "hybrid"
            
            choices.append("4. Cancel")
            choice_map["4"] = "none"
            
            for choice in choices:
                print(f"  {choice}")
            
            user_choice = input(f"\nEnter choice (1-{len(choices)}): ").strip()
            
            return choice_map.get(user_choice, "none")
                
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled by user")
            return "none"
    
    def analyze_file_list(self, 
                         file_paths: List[str], 
                         mode: Optional[str] = None) -> None:
        """Analyze a specific list of files"""
        files = [Path(f) for f in file_paths]
        
        # Validate files exist
        valid_files = []
        for file in files:
            if file.exists():
                valid_files.append(file)
            else:
                logger.warning(f"File not found: {file}")
        
        if not valid_files:
            logger.error("No valid files to process")
            return
        
        # Get analysis capabilities
        stats = self.router.get_analysis_stats()
        
        # Determine analysis mode
        if mode is None:
            mode = self._prompt_for_mode(stats)
        
        if mode == "none":
            logger.info("Analysis cancelled by user")
            return
        
        # Process each file
        success_count = 0
        failure_count = 0
        
        for i, file in enumerate(valid_files, 1):
            print(f"\n[{i}/{len(valid_files)}] Processing: {file.name}")
            
            try:
                result = self.router.analyze_transcript(file, mode)
                
                if result.get("status") == "completed":
                    success_count += 1
                    logger.info(f"✅ Analysis completed: {file.name}")
                else:
                    failure_count += 1
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"❌ Analysis failed: {file.name} - {error_msg}")
                    
            except Exception as e:
                failure_count += 1
                logger.error(f"❌ Exception analyzing {file.name}: {e}")
        
        # Summary
        print(f"\n📊 Analysis Complete:")
        print(f"  ✅ Successful: {success_count}")
        print(f"  ❌ Failed: {failure_count}")

def main():
    """Command line interface"""
    parser = argparse.ArgumentParser(description="Batch analyze existing transcripts")
    parser.add_argument("path", nargs="?", help="Directory or file to analyze")
    parser.add_argument("--mode", choices=["local", "cloud", "hybrid"], 
                       help="Analysis mode (will prompt if not specified)")
    parser.add_argument("--recursive", "-r", action="store_true", default=True,
                       help="Recursively search subdirectories (default)")
    parser.add_argument("--no-recursive", action="store_false", dest="recursive",
                       help="Don't search subdirectories")
    parser.add_argument("--dry-run", "-n", action="store_true",
                       help="Show what would be analyzed without doing it")
    parser.add_argument("--files", nargs="+", help="Specific files to analyze")
    
    args = parser.parse_args()
    
    analyzer = BatchAnalyzer()
    
    if args.files:
        # Analyze specific files
        analyzer.analyze_file_list(args.files, args.mode)
    elif args.path:
        # Analyze directory
        analyzer.analyze_directory(args.path, args.mode, args.recursive, args.dry_run)
    else:
        # Default: analyze current workspace
        current_dir = Path.cwd()
        print(f"No path specified, analyzing current directory: {current_dir}")
        analyzer.analyze_directory(str(current_dir), args.mode, args.recursive, args.dry_run)

if __name__ == "__main__":
    main()