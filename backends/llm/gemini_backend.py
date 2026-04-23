import os
import json
from google import genai
from google.genai import types

def generate_text(prompt: str, config: dict) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing. Please set it in the environment settings to use the Cloud LLM.")
    
    try:
        client = genai.Client(api_key=api_key)
        
        system_instruction = (
            "You are a strict JSON-only API. You must output ONLY valid JSON format. "
            "Do NOT output markdown. Do NOT output conversational text. "
            "Use double quotes for strings. Be precise."
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini API Error: {e}")
