import os
import json
import time

def generate_text(prompt: str, config: dict) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing. Please set it in the environment settings to use the Cloud LLM.")
    
    system_instruction = (
        "You are a strict JSON-only API. You must output ONLY valid JSON format. "
        "Do NOT output markdown. Do NOT output conversational text. "
        "Use double quotes for strings. Be precise."
    )
    
    temperature = float(config.get("temperature", 0.7))
    
    def attempt_gen():
        try:
            try:
                import google.auth
            except ImportError:
                raise RuntimeError("Missing auth dependencies. Please run setup.sh again.")
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=temperature,
                ),
            )
            return response.text
        except ImportError:
            import google.generativeai as genai_old
            genai_old.configure(api_key=api_key)
            
            model = genai_old.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=system_instruction
            )
            response = model.generate_content(
                prompt,
                generation_config=genai_old.types.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=temperature,
                )
            )
            return response.text

    max_retries = 3
    for attempt in range(max_retries):
        try:
            return attempt_gen()
        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Gemini API Error after {max_retries} attempts: {e}")
            error_str = str(e).lower()
            if "503" in error_str or "429" in error_str or "unavailable" in error_str or "exhausted" in error_str:
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"Gemini API Error: {e}")

