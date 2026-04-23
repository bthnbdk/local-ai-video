import urllib.request
import urllib.error
import json

def generate_text(prompt: str, config: dict) -> str:
    host = config.get("host", "http://localhost:1234")
    model = config.get("model", "local-model")
    
    # 1. Reachability Check
    try:
        req_health = urllib.request.Request(f"{host}/v1/models")
        with urllib.request.urlopen(req_health, timeout=5) as r:
            pass # Server is reachable
    except (urllib.error.URLError, ConnectionError) as e:
        raise ConnectionError(f"LM Studio Server not started at {host}. Please launch LM Studio and start the local server. Error: {e}")
    
    # 2. Strict Prompting (Gemma Optimization)
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
        "temperature": 0.7
    }
    
    try:
        req = urllib.request.Request(
            f"{host}/v1/chat/completions", 
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            response_data = json.loads(r.read().decode())
            return response_data["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"LM Studio backend error: {e}")
