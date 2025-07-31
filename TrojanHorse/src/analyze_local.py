#!/usr/bin/env python3
"""
TrojanHorse Local Analysis Module
Processes transcripts using local qwen3:8b model via Ollama for privacy-first content analysis.
"""

import json
import re
import requests
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LocalAnalyzer:
    """Local transcript analysis using qwen3:8b via Ollama"""
    
    def __init__(self, 
                 model: str = "qwen3:8b",
                 endpoint: str = "http://localhost:11434/api/generate",
                 prompt_file: str = "prompts/local_analysis.txt"):
        self.model = model
        self.endpoint = endpoint
        self.prompt_file = Path(prompt_file)
        self.base_path = Path("/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes").expanduser()
        
        # Load prompt template
        self.prompt_template = self._load_prompt_template()
        
        # PII patterns for privacy protection
        self.pii_patterns = {
            'phone': re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            'credit_card': re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
            'names': re.compile(r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b'),
            'addresses': re.compile(r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b', re.IGNORECASE)
        }
        
    def _load_prompt_template(self) -> str:
        """Load the editable prompt template"""
        if not self.prompt_file.exists():
            logger.warning(f"Prompt file {self.prompt_file} not found, using default")
            return self._get_default_prompt()
        
        try:
            return self.prompt_file.read_text()
        except Exception as e:
            logger.error(f"Error loading prompt template: {e}")
            return self._get_default_prompt()
    
    def _get_default_prompt(self) -> str:
        """Default prompt template if file is missing"""
        return """Analyze this transcript and return JSON with content_type, confidence, key_points, action_items, topics, decisions, summary, people_mentioned, projects_referenced, privacy_score (1-10), and urgency_level (1-5).

TRANSCRIPT:
{transcript}"""
    
    def _detect_pii(self, text: str) -> Dict[str, List[str]]:
        """Detect PII in text and return findings"""
        pii_found = {}
        
        for pii_type, pattern in self.pii_patterns.items():
            matches = pattern.findall(text)
            if matches:
                pii_found[pii_type] = matches
                
        return pii_found
    
    def _calculate_privacy_score(self, text: str, pii_found: Dict[str, List[str]]) -> int:
        """Calculate privacy score based on content and PII"""
        score = 1  # Base score
        
        # Increase score based on PII types found
        if 'ssn' in pii_found or 'credit_card' in pii_found:
            score += 8
        if 'phone' in pii_found or 'email' in pii_found:
            score += 3
        if 'names' in pii_found:
            score += 2
        if 'addresses' in pii_found:
            score += 2
            
        # Check for sensitive keywords
        sensitive_keywords = [
            'password', 'secret', 'confidential', 'private', 'personal',
            'salary', 'compensation', 'medical', 'health', 'diagnosis',
            'therapy', 'counseling', 'intimate', 'relationship'
        ]
        
        text_lower = text.lower()
        sensitive_count = sum(1 for keyword in sensitive_keywords if keyword in text_lower)
        score += min(sensitive_count, 3)  # Cap at 3 points
        
        return min(score, 10)  # Cap at 10
    
    def _query_ollama(self, prompt: str) -> Optional[str]:
        """Query Ollama API with retry logic"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 2048
            }
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.endpoint,
                    json=payload,
                    timeout=120  # 2 minute timeout
                )
                response.raise_for_status()
                
                result = response.json()
                return result.get('response', '').strip()
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"All attempts failed to query Ollama: {e}")
                    return None
        
        return None
    
    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """Parse JSON response from model, handling various formats"""
        if not response:
            return None
            
        # Try to find JSON block in response
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',  # JSON in code block
            r'```\s*(\{.*?\})\s*```',      # JSON in generic code block
            r'(\{.*\})',                   # Raw JSON
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                try:
                    return json.loads(matches[0])
                except json.JSONDecodeError:
                    continue
        
        # If no JSON found, try parsing the entire response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"Could not parse JSON from response: {response[:200]}...")
            return None
    
    def process_transcript(self, transcript_file: Union[str, Path]) -> Optional[Dict]:
        """Process a single transcript file"""
        transcript_path = Path(transcript_file)
        
        if not transcript_path.exists():
            logger.error(f"Transcript file not found: {transcript_path}")
            return None
            
        try:
            # Read transcript
            transcript_text = transcript_path.read_text(encoding='utf-8')
            logger.info(f"Processing transcript: {transcript_path.name} ({len(transcript_text)} chars)")
            
            # Skip very short transcripts
            if len(transcript_text.strip()) < 50:
                logger.info("Transcript too short, skipping")
                return None
            
            # Detect PII
            pii_found = self._detect_pii(transcript_text)
            privacy_score = self._calculate_privacy_score(transcript_text, pii_found)
            
            # Prepare prompt
            prompt = self.prompt_template.format(transcript=transcript_text)
            
            # Query model
            response = self._query_ollama(prompt)
            if not response:
                logger.error("Failed to get response from Ollama")
                return None
            
            # Parse response
            logger.info(f"Raw model response: {response[:500]}...")
            analysis = self._parse_json_response(response)
            if not analysis:
                logger.error("Failed to parse analysis from model response")
                return None
            
            # Add metadata
            analysis['file_path'] = str(transcript_path)
            analysis['processed_at'] = datetime.now().isoformat()
            analysis['model_used'] = self.model
            analysis['pii_detected'] = pii_found
            analysis['calculated_privacy_score'] = privacy_score
            
            # Override privacy score if our calculation is higher
            if 'privacy_score' in analysis:
                analysis['privacy_score'] = max(analysis['privacy_score'], privacy_score)
            else:
                analysis['privacy_score'] = privacy_score
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error processing transcript {transcript_path}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None
    
    def save_analysis(self, analysis: Dict, output_file: Optional[Union[str, Path]] = None) -> bool:
        """Save analysis to JSON file"""
        if not analysis:
            return False
            
        try:
            if output_file is None:
                # Generate output filename based on original file
                original_path = Path(analysis['file_path'])
                output_file = original_path.with_suffix('.analysis.json')
            else:
                output_file = Path(output_file)
            
            with output_file.open('w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Analysis saved to: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving analysis: {e}")
            return False
    
    def process_daily_folder(self, date_str: Optional[str] = None) -> List[Dict]:
        """Process all transcripts in a daily folder"""
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        daily_folder = self.base_path / date_str / "transcribed_audio"
        
        if not daily_folder.exists():
            logger.warning(f"Daily folder not found: {daily_folder}")
            return []
        
        # Find all transcript files
        transcript_files = list(daily_folder.glob("*.txt"))
        logger.info(f"Found {len(transcript_files)} transcript files in {daily_folder}")
        
        results = []
        for transcript_file in transcript_files:
            # Skip if analysis already exists
            analysis_file = transcript_file.with_suffix('.analysis.json')
            if analysis_file.exists():
                logger.info(f"Analysis already exists for {transcript_file.name}, skipping")
                continue
            
            analysis = self.process_transcript(transcript_file)
            if analysis:
                if self.save_analysis(analysis):
                    results.append(analysis)
        
        logger.info(f"Processed {len(results)} new transcripts")
        return results
    
    def batch_process(self, start_date: str, end_date: Optional[str] = None) -> List[Dict]:
        """Process multiple days of transcripts"""
        from datetime import datetime, timedelta
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else start
        
        results = []
        current = start
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            daily_results = self.process_daily_folder(date_str)
            results.extend(daily_results)
            current += timedelta(days=1)
        
        return results

def main():
    """Command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='TrojanHorse Local Analysis')
    parser.add_argument('--file', type=str, help='Process single transcript file')
    parser.add_argument('--date', type=str, help='Process daily folder (YYYY-MM-DD)')
    parser.add_argument('--batch', action='store_true', help='Process all pending transcripts from today')
    parser.add_argument('--start-date', type=str, help='Start date for batch processing (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date for batch processing (YYYY-MM-DD)')
    parser.add_argument('--test', action='store_true', help='Test Ollama connection')
    
    args = parser.parse_args()
    
    analyzer = LocalAnalyzer()
    
    if args.test:
        # Test Ollama connection
        response = analyzer._query_ollama("Respond with 'OK' if you can process this message.")
        if response:
            print(f"✅ Ollama connection successful: {response}")
        else:
            print("❌ Ollama connection failed")
        return
    
    if args.file:
        analysis = analyzer.process_transcript(args.file)
        if analysis:
            analyzer.save_analysis(analysis)
            print(f"✅ Processed: {args.file}")
        else:
            print(f"❌ Failed to process: {args.file}")
    
    elif args.date:
        results = analyzer.process_daily_folder(args.date)
        print(f"✅ Processed {len(results)} transcripts for {args.date}")
    
    elif args.batch:
        results = analyzer.process_daily_folder()
        print(f"✅ Processed {len(results)} new transcripts")
    
    elif args.start_date:
        results = analyzer.batch_process(args.start_date, args.end_date)
        print(f"✅ Processed {len(results)} transcripts total")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()