import urllib.request
import json
import urllib.error

def generate_text(prompt: str, config: dict) -> str:
    host = config.get("host", "http://localhost:11434")
    model = config.get("model", "mistral:7b-instruct-q4_K_M")
    
    try:
        req = urllib.request.Request(f"{host}/api/generate", 
            data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode())["response"]
    except (urllib.error.URLError, ConnectionError) as e:
        raise ConnectionError(f"Ollama is not running. Please run 'ollama serve'. Error: {e}")
    except Exception as e:
        raise RuntimeError(f"Ollama backend failure: {e}")
