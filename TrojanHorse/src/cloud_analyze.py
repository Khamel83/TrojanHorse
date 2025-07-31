"""
Cloud analysis module for TrojanHorse Context Capture System.

This module provides cloud-based AI analysis using OpenRouter API with Gemini Flash 2.0.
Integrates with the existing transcription pipeline to provide advanced insights.
"""

import json
import os
import requests
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json file."""
    config_path = os.path.join(os.path.dirname(__file__), 'workspace', 'config.json')
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found at {config_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file: {e}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
def analyze(text: str, prompt: str) -> str:
    """
    Analyze text using cloud AI via OpenRouter API.
    
    Args:
        text (str): The text content to analyze
        prompt (str): The analysis prompt/instruction
        
    Returns:
        str: Analysis results from the cloud AI
        
    Raises:
        ValueError: If API key is missing or invalid
        requests.RequestException: If API request fails
    """
    # Load configuration
    config = load_config()
    cloud_config = config.get('cloud_analysis', {})
    
    api_key = cloud_config.get('openrouter_api_key')
    model = cloud_config.get('model', 'google/gemini-2.0-flash-001')
    base_url = cloud_config.get('base_url', 'https://openrouter.ai/api/v1')
    
    if not api_key or api_key == "YOUR_OPENROUTER_API_KEY_HERE":
        raise ValueError("OpenRouter API key not configured. Please set openrouter_api_key in config.json")
    
    # Prepare the API request
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://github.com/Khamel83/TrojanHorse',
        'X-Title': 'TrojanHorse Context Capture'
    }
    
    # Combine prompt and text for analysis
    messages = [
        {
            "role": "system",
            "content": prompt
        },
        {
            "role": "user", 
            "content": text
        }
    ]
    
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 4000,
        "temperature": 0.3
    }
    
    try:
        # Make the API request
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        response.raise_for_status()
        
        # Parse the response
        result = response.json()
        
        if 'choices' not in result or not result['choices']:
            raise ValueError("Invalid response format from OpenRouter API")
            
        analysis = result['choices'][0]['message']['content']
        return analysis.strip()
        
    except requests.exceptions.Timeout:
        raise requests.RequestException("Request timed out. The API may be experiencing delays.")
    except requests.exceptions.ConnectionError:
        raise requests.RequestException("Connection error. Please check your internet connection.")
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            raise ValueError("Invalid API key. Please check your OpenRouter API key in config.json")
        elif response.status_code == 429:
            raise requests.RequestException("Rate limit exceeded. Please try again later.")
        else:
            raise requests.RequestException(f"HTTP error {response.status_code}: {e}")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON response from OpenRouter API")


def test_connection() -> bool:
    """
    Test the connection to OpenRouter API.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        result = analyze("Hello", "Respond with just 'OK' if you can understand this message.")
        return "OK" in result or "ok" in result.lower()
    except Exception:
        return False


if __name__ == "__main__":
    # Basic test when run directly
    print("Testing cloud analysis connection...")
    
    if test_connection():
        print("✅ Connection successful!")
        
        # Demo analysis
        sample_text = "The meeting discussed quarterly goals and budget allocation for the marketing team."
        sample_prompt = "Summarize the key points and extract any action items from this text."
        
        try:
            result = analyze(sample_text, sample_prompt)
            print(f"\n📝 Sample Analysis:\n{result}")
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
    else:
        print("❌ Connection failed. Please check your API key and configuration.")