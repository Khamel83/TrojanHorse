import ollama

def summarize(text: str) -> str:
    """Summarizes the given text using the Ollama LLM."""
    # Placeholder for actual summarization logic
    response = ollama.chat(model='qwen3:8b', messages=[
        {
            'role': 'user',
            'content': f'Summarize the following text: {text}',
        },
    ])
    return response['message']['content']

def extract_action_items(text: str) -> list[str]:
    """Extracts action items from the given text using the Ollama LLM."""
    # Placeholder for actual action item extraction logic
    response = ollama.chat(model='qwen3:8b', messages=[
        {
            'role': 'user',
            'content': f'Extract action items from the following text: {text}. List each action item on a new line.',
        },
    ])
    return [item.strip() for item in response['message']['content'].split('\n') if item.strip()]

if __name__ == "__main__":
    # Example Usage
    sample_text = """
    During our meeting, we discussed several key points. First, we need to finalize the Q3 budget by next Friday. John will be responsible for collecting all department-specific figures. Second, Sarah needs to update the client presentation with the new marketing data. This should be done by end of day Tuesday. Finally, we decided to schedule a follow-up meeting for next Monday to review progress. Please ensure all action items are completed before then.
    """

    print("Summarizing text...")
    summary = summarize(sample_text)
    print("\nSummary:")
    print(summary)

    print("\nExtracting action items...")
    action_items = extract_action_items(sample_text)
    print("\nAction Items:")
    for item in action_items:
        print(f"- {item}")

