import os
import json
from backends.tts.kokoro_backend import generate_audio
from core.memory_orchestrator import orchestrator

def run(project_dir: str, config: dict, log_cb=None):
    script_file = os.path.join(project_dir, "script.json")
    if not os.path.exists(script_file):
        raise FileNotFoundError(f"Missing {script_file}")
        
    with open(script_file, "r") as f:
        script = json.load(f)
        
    # extract concatenated text with 1s pauses (handled by concatenating strings with padding logic in TTS backend or here)
    texts = [scene["text"] for scene in script.get("scenes", [])]
    full_text = " \n".join(texts)
    
    # RAM Check & model load
    orchestrator.load_model("kokoro_tts", lambda: None, required_ram_gb=1.0)
    
    out_path = os.path.join(project_dir, "audio.wav")
    
    if log_cb: log_cb("Generating TTS audio...")
    # call backend
    generate_audio(full_text, out_path, config.get("tts", {}))
    
    if log_cb: log_cb(f"TTS finished. Audio saved to {out_path}")
    return True
