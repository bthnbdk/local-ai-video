import os
import json
import time
import requests

def generate_text(prompt: str, config: dict) -> str:
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise ValueError("XAI_API_KEY environment variable is missing. Please set it to use Grok LLM.")
        
    model = config.get("model", "grok-2-latest")
    
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    system_instruction = (
        "You are a strict JSON-only API. You must output ONLY valid JSON format. "
        "Do NOT output markdown. Do NOT output conversational text. "
        "Use double quotes for strings. Be precise."
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }
    
    def attempt_gen():
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"x.ai LLM API Error: {resp.status_code} - {resp.text}")
        
        try:
            res_data = resp.json()
            return res_data["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Failed to parse x.ai response: {str(e)}")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            return attempt_gen()
        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"x.ai LLM Error after {max_retries} attempts: {e}")
            error_str = str(e).lower()
            if "503" in error_str or "429" in error_str or "unavailable" in error_str or "too many requests" in error_str:
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"x.ai LLM API Error: {e}")

