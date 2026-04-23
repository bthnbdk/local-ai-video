import urllib.request
import json

def generate_text(prompt: str, config: dict) -> str:
    host = config.get("host", "http://localhost:1234")
    model = config.get("model", "local-model")
    
    try:
        req = urllib.request.Request(f"{host}/v1/chat/completions", 
            data=json.dumps({
                "model": model, 
                "messages": [{"role": "user", "content": prompt}], 
                "temperature": 0.7
            }).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"LMStudio backend error: {e}")
        return ""
