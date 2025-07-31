#!/usr/bin/env python3
"""
Batch Indexer for TrojanHorse Context Capture System
Phase 3: Search Engine Foundation - Retroactively index existing transcripts
"""

import os
import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse

from search_engine import SearchEngine

class BatchIndexer:
    """Batch indexer for existing TrojanHorse transcripts and analysis files"""
    
    def __init__(self, base_path: str, db_path: str = "trojan_search.db"):
        self.base_path = Path(base_path)
        self.search_engine = SearchEngine(db_path)
        self.logger = logging.getLogger(__name__)
        
        # Statistics
        self.stats = {
            'transcripts_processed': 0,
            'transcripts_added': 0,
            'analysis_processed': 0,
            'analysis_added': 0,
            'errors': 0
        }
    
    def index_all(self) -> Dict:
        """Index all transcripts and analysis files in the base path"""
        self.logger.info(f"Starting batch indexing from: {self.base_path}")
        
        if not self.base_path.exists():
            raise FileNotFoundError(f"Base path does not exist: {self.base_path}")
        
        # Find all date directories (YYYY-MM-DD format)
        date_dirs = []
        for item in self.base_path.iterdir():
            if item.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}', item.name):
                date_dirs.append(item)
        
        self.logger.info(f"Found {len(date_dirs)} date directories to process")
        
        for date_dir in sorted(date_dirs):
            self._process_date_directory(date_dir)
        
        self.logger.info(f"Batch indexing complete. Stats: {self.stats}")
        return self.stats
    
    def _process_date_directory(self, date_dir: Path):
        """Process all files in a date directory"""
        self.logger.info(f"Processing directory: {date_dir.name}")
        
        # Find transcript files
        transcript_files = []
        
        # Check different possible locations for transcripts
        possible_paths = [
            date_dir,  # Root of date directory
            date_dir / "transcribed_audio",  # Standard location
            date_dir / "audio",  # Alternative location
        ]
        
        for path in possible_paths:
            if path.exists():
                transcript_files.extend(path.glob("*.txt"))
        
        # Process each transcript file
        for transcript_file in transcript_files:
            try:
                self._process_transcript_file(transcript_file, date_dir.name)
            except Exception as e:
                self.logger.error(f"Error processing transcript {transcript_file}: {e}")
                self.stats['errors'] += 1
    
    def _process_transcript_file(self, transcript_file: Path, date_str: str):
        """Process a single transcript file"""
        self.stats['transcripts_processed'] += 1
        
        try:
            # Read transcript content
            content = transcript_file.read_text(encoding='utf-8')
            
            # Parse transcript header for metadata
            metadata = self._parse_transcript_metadata(content)
            
            # Extract clean content (remove header)
            clean_content = self._extract_clean_content(content)
            
            if not clean_content.strip():
                self.logger.warning(f"Empty transcript content: {transcript_file}")
                return
            
            # Add to search database
            transcript_id = self.search_engine.add_transcript(
                filename=transcript_file.name,
                date_str=date_str,
                timestamp_str=metadata.get('timestamp', f"{date_str}T00:00:00"),
                engine=metadata.get('engine', 'unknown'),
                file_path=str(transcript_file),
                content=clean_content
            )
            
            self.stats['transcripts_added'] += 1
            self.logger.debug(f"Added transcript: {transcript_file.name} (ID: {transcript_id})")
            
            # Look for corresponding analysis file
            analysis_file = self._find_analysis_file(transcript_file)
            if analysis_file and analysis_file.exists():
                self._process_analysis_file(analysis_file, transcript_id)
            
        except Exception as e:
            self.logger.error(f"Failed to process transcript {transcript_file}: {e}")
            self.stats['errors'] += 1
            raise
    
    def _parse_transcript_metadata(self, content: str) -> Dict:
        """Parse metadata from transcript header"""
        metadata = {}
        lines = content.split('\n')
        
        for line in lines[:10]:  # Check first 10 lines for metadata
            line = line.strip()
            
            # Look for timestamp
            if line.startswith('Generated:'):
                timestamp_str = line.split('Generated:', 1)[1].strip()
                try:
                    # Try to parse different timestamp formats
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                        try:
                            dt = datetime.strptime(timestamp_str, fmt)
                            metadata['timestamp'] = dt.isoformat()
                            break
                        except ValueError:
                            continue
                except:
                    pass
            
            # Look for engine
            elif line.startswith('Engine:'):
                metadata['engine'] = line.split('Engine:', 1)[1].strip()
            
            # Stop at content separator
            elif line.startswith('---'):
                break
        
        return metadata
    
    def _extract_clean_content(self, content: str) -> str:
        """Extract clean transcript content without metadata header"""
        lines = content.split('\n')
        content_start = 0
        
        # Find the end of the header (marked by --- or empty lines)
        for i, line in enumerate(lines):
            if line.strip().startswith('---') or (i > 5 and not line.strip()):
                content_start = i + 1
                break
        
        # Join remaining lines and clean up
        clean_content = '\n'.join(lines[content_start:]).strip()
        return clean_content
    
    def _find_analysis_file(self, transcript_file: Path) -> Optional[Path]:
        """Find corresponding analysis file for a transcript"""
        # Try different analysis file patterns
        base_name = transcript_file.stem
        analysis_patterns = [
            f"{base_name}.analysis.md",
            f"{base_name}_analysis.md",
            f"{base_name}.md"
        ]
        
        # Check in same directory and parent directory
        search_dirs = [transcript_file.parent, transcript_file.parent.parent]
        
        for search_dir in search_dirs:
            for pattern in analysis_patterns:
                analysis_file = search_dir / pattern
                if analysis_file.exists():
                    return analysis_file
        
        return None
    
    def _process_analysis_file(self, analysis_file: Path, transcript_id: int):
        """Process an analysis file"""
        self.stats['analysis_processed'] += 1
        
        try:
            content = analysis_file.read_text(encoding='utf-8')
            analysis_data = self._parse_analysis_content(content)
            
            # Add to search database
            analysis_id = self.search_engine.add_analysis(
                transcript_id=transcript_id,
                mode=analysis_data.get('mode', 'unknown'),
                model=analysis_data.get('model', 'unknown'),
                summary=analysis_data.get('summary', ''),
                action_items=analysis_data.get('action_items', []),
                tags=analysis_data.get('tags', []),
                classification=analysis_data.get('classification', 'unknown'),
                sentiment=analysis_data.get('sentiment', 'neutral'),
                confidence=analysis_data.get('confidence', 0.5),
                file_path=str(analysis_file)
            )
            
            self.stats['analysis_added'] += 1
            self.logger.debug(f"Added analysis: {analysis_file.name} (ID: {analysis_id})")
            
        except Exception as e:
            self.logger.error(f"Failed to process analysis {analysis_file}: {e}")
            self.stats['errors'] += 1
            raise
    
    def _parse_analysis_content(self, content: str) -> Dict:
        """Parse analysis content from markdown file"""
        analysis_data = {
            'mode': 'unknown',
            'model': 'unknown',
            'summary': '',
            'action_items': [],
            'tags': [],
            'classification': 'unknown',
            'sentiment': 'neutral',
            'confidence': 0.5
        }
        
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line_clean = line.strip()
            
            # Parse metadata from header
            if line_clean.startswith('**Mode:**'):
                analysis_data['mode'] = line_clean.split('**Mode:**', 1)[1].strip()
            elif line_clean.startswith('**Model:**'):
                analysis_data['model'] = line_clean.split('**Model:**', 1)[1].strip()
            
            # Parse sections
            elif line_clean.startswith('## '):
                # Save previous section
                if current_section and current_content:
                    self._save_section_content(analysis_data, current_section, current_content)
                
                # Start new section
                current_section = line_clean[3:].lower()
                current_content = []
            
            elif line_clean and current_section:
                current_content.append(line_clean)
        
        # Save last section
        if current_section and current_content:
            self._save_section_content(analysis_data, current_section, current_content)
        
        return analysis_data
    
    def _save_section_content(self, analysis_data: Dict, section: str, content: List[str]):
        """Save parsed section content to analysis data"""
        content_text = '\n'.join(content).strip()
        
        if section == 'summary':
            analysis_data['summary'] = content_text
        
        elif section == 'action items':
            # Extract action items (look for numbered or bulleted lists)
            items = []
            for line in content:
                # Remove markdown formatting and numbering
                cleaned = re.sub(r'^\d+\.\s*', '', line)
                cleaned = re.sub(r'^[\-\*]\s*', '', cleaned)
                cleaned = cleaned.strip()
                if cleaned:
                    items.append(cleaned)
            analysis_data['action_items'] = items
        
        elif section in ['tags', 'categories']:
            # Extract tags (look for comma-separated or listed items)
            tags = []
            content_str = ' '.join(content)
            # Split by common separators
            for separator in [',', ';', '\n', '•', '-']:
                if separator in content_str:
                    parts = content_str.split(separator)
                    tags = [tag.strip() for tag in parts if tag.strip()]
                    break
            analysis_data['tags'] = tags
        
        elif section in ['classification', 'type', 'category']:
            analysis_data['classification'] = content[0] if content else 'unknown'
    
    def close(self):
        """Close the search engine connection"""
        self.search_engine.close()

def main():
    """Command-line interface for batch indexer"""
    parser = argparse.ArgumentParser(description='Batch index TrojanHorse transcripts')
    parser.add_argument('--base-path', '-p', required=True,
                       help='Base path containing date directories with transcripts')
    parser.add_argument('--database', '-d', default='trojan_search.db',
                       help='SQLite database path')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run batch indexing
    indexer = BatchIndexer(args.base_path, args.database)
    
    try:
        stats = indexer.index_all()
        print(f"\nBatch indexing completed:")
        print(f"  Transcripts processed: {stats['transcripts_processed']}")
        print(f"  Transcripts added: {stats['transcripts_added']}")
        print(f"  Analysis processed: {stats['analysis_processed']}")
        print(f"  Analysis added: {stats['analysis_added']}")
        print(f"  Errors: {stats['errors']}")
        
    except Exception as e:
        logging.error(f"Batch indexing failed: {e}")
        return 1
    
    finally:
        indexer.close()
    
    return 0

if __name__ == "__main__":
    exit(main())