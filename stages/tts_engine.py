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
    
    tts_backend = config.get("tts", {}).get("backend", "kokoro")
    
    out_path = os.path.join(project_dir, "audio.wav")
    
    if log_cb: log_cb(f"Generating TTS audio using {tts_backend}...")
    
    if tts_backend == "xai":
        from backends.tts.xai_backend import generate_speech
        generate_speech(full_text, config.get("tts", {}), out_path)
    else:
        # RAM Check & model load
        orchestrator.load_model("kokoro_tts", lambda: None, required_ram_gb=1.0)
        from backends.tts.kokoro_backend import generate_audio
        generate_audio(full_text, out_path, config.get("tts", {}))
    
    if log_cb: log_cb(f"TTS finished. Audio saved to {out_path}")
    return True
