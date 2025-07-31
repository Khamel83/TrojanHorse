#!/usr/bin/env python3
"""
TrojanHorse Gemini Processing Module
Advanced analysis using Gemini Flash 2.0 via OpenRouter for strategic insights and pattern recognition.
"""

import json
import os
import re
import requests
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GeminiProcessor:
    """Advanced analysis using Gemini Flash 2.0 via OpenRouter"""
    
    def __init__(self,
                 model: str = "google/gemini-2.0-flash-001",
                 api_key_env: str = "OPENROUTER_API_KEY",
                 endpoint: str = "https://openrouter.ai/api/v1/chat/completions",
                 prompt_file: str = "prompts/gemini_analysis.txt",
                 cost_limit_daily: float = 0.20):
        
        self.model = model
        self.endpoint = endpoint
        self.prompt_file = Path(prompt_file)
        self.cost_limit_daily = cost_limit_daily
        
        # Load API key
        self.api_key = os.getenv(api_key_env)
        if not self.api_key:
            raise ValueError(f"API key not found in environment variable: {api_key_env}")
        
        self.base_path = Path("/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes")
        
        # Load prompt template
        self.prompt_template = self._load_prompt_template()
        
        # Cost tracking
        self.cost_tracker_file = Path("logs/gemini_costs.json")
        self.cost_tracker_file.parent.mkdir(exist_ok=True)
        
        # Rate limiting
        self.last_request_time = 0
        self.min_interval = 6  # 10 requests per minute max
        
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
        return """Analyze these conversation summaries for strategic insights and patterns.

SUMMARIES:
{summaries}

Return JSON with strategic_insights, project_progress, decision_tracking, patterns_identified, recommendations, and cross_references."""
    
    def _check_daily_cost_limit(self) -> bool:
        """Check if daily cost limit has been reached"""
        try:
            if not self.cost_tracker_file.exists():
                return True
            
            with open(self.cost_tracker_file, 'r') as f:
                costs = json.load(f)
            
            today = datetime.now().strftime('%Y-%m-%d')
            daily_costs = costs.get(today, {})
            total_cost = sum(daily_costs.values())
            
            return total_cost < self.cost_limit_daily
            
        except Exception as e:
            logger.error(f"Error checking cost limit: {e}")
            return True  # Allow if we can't check
    
    def _log_api_cost(self, estimated_cost: float):
        """Log API usage cost"""
        try:
            costs = {}
            if self.cost_tracker_file.exists():
                with open(self.cost_tracker_file, 'r') as f:
                    costs = json.load(f)
            
            today = datetime.now().strftime('%Y-%m-%d')
            timestamp = datetime.now().isoformat()
            
            if today not in costs:
                costs[today] = {}
            
            costs[today][timestamp] = estimated_cost
            
            with open(self.cost_tracker_file, 'w') as f:
                json.dump(costs, f, indent=2)
                
            logger.info(f"Logged API cost: ${estimated_cost:.4f}")
            
        except Exception as e:
            logger.error(f"Error logging cost: {e}")
    
    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate API cost based on token usage"""
        # Gemini Flash 2.0 pricing (approximate)
        input_cost_per_token = 0.0000002  # $0.0002 per 1K tokens
        output_cost_per_token = 0.0000008  # $0.0008 per 1K tokens
        
        return (input_tokens * input_cost_per_token) + (output_tokens * output_cost_per_token)
    
    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            logger.info(f"Rate limiting: sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _query_gemini(self, prompt: str, max_tokens: int = 8192) -> Optional[Dict]:
        """Query Gemini API via OpenRouter"""
        if not self._check_daily_cost_limit():
            logger.warning("Daily cost limit reached, skipping Gemini processing")
            return None
        
        self._rate_limit()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Khamel83/TrojanHorse",
            "X-Title": "TrojanHorse Context Capture"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "top_p": 0.9
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Querying Gemini API (attempt {attempt + 1})")
                response = requests.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Extract response and usage
                if 'choices' in result and result['choices']:
                    content = result['choices'][0]['message']['content']
                    
                    # Log costs if usage info available
                    if 'usage' in result:
                        usage = result['usage']
                        estimated_cost = self._estimate_cost(
                            usage.get('prompt_tokens', 0),
                            usage.get('completion_tokens', 0)
                        )
                        self._log_api_cost(estimated_cost)
                    
                    return {
                        'content': content,
                        'usage': result.get('usage', {}),
                        'model': result.get('model', self.model)
                    }
                else:
                    logger.error(f"Unexpected API response format: {result}")
                    return None
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"All attempts failed to query Gemini: {e}")
                    return None
        
        return None
    
    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """Parse JSON response from Gemini"""
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
            logger.error(f"Could not parse JSON from Gemini response: {response[:200]}...")
            return None
    
    def _sanitize_summaries(self, summaries: List[Dict]) -> List[Dict]:
        """Sanitize summaries before sending to external API"""
        sanitized = []
        
        for summary in summaries:
            # Only send specific fields, exclude sensitive data
            sanitized_summary = {
                'date': summary.get('processed_at', '')[:10],  # Just date, not full timestamp
                'content_type': summary.get('content_type'),
                'summary': summary.get('summary', ''),
                'key_points': summary.get('key_points', []),
                'action_items': [
                    {
                        'item': item.get('item', ''),
                        'priority': item.get('priority', ''),
                        'deadline': item.get('deadline')
                    } for item in summary.get('action_items', [])
                ],
                'topics': summary.get('topics', []),
                'decisions': summary.get('decisions', []),
                'projects_referenced': summary.get('projects_referenced', [])
            }
            
            # Only include if privacy score is acceptable (≤ 7)
            if summary.get('privacy_score', 10) <= 7:
                sanitized.append(sanitized_summary)
            else:
                logger.info(f"Skipping high-privacy content (score: {summary.get('privacy_score')})")
        
        return sanitized
    
    def process_summaries(self, summaries: List[Dict]) -> Optional[Dict]:
        """Process a batch of local analysis summaries"""
        if not summaries:
            logger.warning("No summaries provided for processing")
            return None
        
        logger.info(f"Processing {len(summaries)} summaries with Gemini")
        
        # Sanitize summaries for external processing
        sanitized_summaries = self._sanitize_summaries(summaries)
        
        if not sanitized_summaries:
            logger.warning("No summaries passed privacy filtering")
            return None
        
        logger.info(f"Sending {len(sanitized_summaries)} sanitized summaries to Gemini")
        
        # Prepare prompt
        summaries_text = json.dumps(sanitized_summaries, indent=2, ensure_ascii=False)
        prompt = self.prompt_template.format(summaries=summaries_text)
        
        # Query Gemini
        result = self._query_gemini(prompt)
        if not result:
            logger.error("Failed to get response from Gemini")
            return None
        
        # Parse response
        analysis = self._parse_json_response(result['content'])
        if not analysis:
            logger.error("Failed to parse analysis from Gemini response")
            return None
        
        # Add metadata
        analysis['processed_at'] = datetime.now().isoformat()
        analysis['model_used'] = result.get('model', self.model)
        analysis['summaries_processed'] = len(sanitized_summaries)
        analysis['api_usage'] = result.get('usage', {})
        
        return analysis
    
    def load_analysis_files(self, date_range: Optional[int] = 7) -> List[Dict]:
        """Load analysis files from the last N days"""
        analyses = []
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=date_range)
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            daily_folder = self.base_path / date_str / "transcribed_audio"
            
            if daily_folder.exists():
                # Find all .analysis.json files
                analysis_files = list(daily_folder.glob("*.analysis.json"))
                
                for analysis_file in analysis_files:
                    try:
                        with open(analysis_file, 'r') as f:
                            analysis = json.load(f)
                            analyses.append(analysis)
                    except Exception as e:
                        logger.error(f"Error loading analysis file {analysis_file}: {e}")
            
            current_date += timedelta(days=1)
        
        logger.info(f"Loaded {len(analyses)} analysis files from last {date_range} days")
        return analyses
    
    def save_analysis(self, analysis: Dict, output_file: Optional[Union[str, Path]] = None) -> bool:
        """Save Gemini analysis to file"""
        if not analysis:
            return False
        
        try:
            if output_file is None:
                # Generate filename based on date range
                today = datetime.now().strftime('%Y-%m-%d')
                timestamp = datetime.now().strftime('%H%M%S')
                output_file = Path(f"logs/gemini_analysis_{today}_{timestamp}.json")
                
                # Also save to today's folder if it exists
                daily_folder = self.base_path / today
                if daily_folder.exists():
                    daily_file = daily_folder / f"gemini_analysis_{timestamp}.json"
                    with open(daily_file, 'w', encoding='utf-8') as f:
                        json.dump(analysis, f, indent=2, ensure_ascii=False)
                    logger.info(f"Analysis saved to daily folder: {daily_file}")
            else:
                output_file = Path(output_file)
            
            # Ensure logs directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Gemini analysis saved to: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving Gemini analysis: {e}")
            return False
    
    def process_recent_content(self, days: int = 7) -> Optional[Dict]:
        """Process content from the last N days"""
        summaries = self.load_analysis_files(days)
        if not summaries:
            logger.warning(f"No analysis files found for last {days} days")
            return None
        
        analysis = self.process_summaries(summaries)
        if analysis:
            self.save_analysis(analysis)
        
        return analysis

def main():
    """Command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='TrojanHorse Gemini Processing')
    parser.add_argument('--days', type=int, default=7, help='Number of days to analyze (default: 7)')
    parser.add_argument('--test', action='store_true', help='Test API connection')
    parser.add_argument('--costs', action='store_true', help='Show cost summary')
    parser.add_argument('--batch-size', type=int, default=10, help='Batch size for processing')
    
    args = parser.parse_args()
    
    try:
        processor = GeminiProcessor()
        
        if args.test:
            # Test API connection
            test_summaries = [{
                'date': '2025-07-30',
                'content_type': 'thinking',
                'summary': 'Test summary for API connection',
                'key_points': ['Test point'],
                'topics': ['testing'],
                'privacy_score': 3
            }]
            
            result = processor.process_summaries(test_summaries)
            if result:
                print("✅ Gemini API connection successful")
                print(f"Strategic insights: {len(result.get('strategic_insights', []))}")
            else:
                print("❌ Gemini API connection failed")
        
        elif args.costs:
            # Show cost summary
            if processor.cost_tracker_file.exists():
                with open(processor.cost_tracker_file, 'r') as f:
                    costs = json.load(f)
                
                print("Cost Summary:")
                total_cost = 0
                for date, daily_costs in costs.items():
                    daily_total = sum(daily_costs.values())
                    total_cost += daily_total
                    print(f"  {date}: ${daily_total:.4f}")
                
                print(f"Total cost: ${total_cost:.4f}")
                print(f"Daily limit: ${processor.cost_limit_daily:.2f}")
            else:
                print("No cost data available")
        
        else:
            # Process recent content
            result = processor.process_recent_content(args.days)
            if result:
                print(f"✅ Processed content from last {args.days} days")
                print(f"Strategic insights: {len(result.get('strategic_insights', []))}")
                print(f"Projects tracked: {len(result.get('project_progress', {}))}")
                print(f"Decisions tracked: {len(result.get('decision_tracking', []))}")
            else:
                print(f"❌ Failed to process content from last {args.days} days")
    
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()