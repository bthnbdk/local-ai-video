import os
import json
import warnings
from core.memory_orchestrator import orchestrator

def run(project_dir: str, config: dict, log_cb=None):
    audio_file = os.path.join(project_dir, "audio.wav")
    if not os.path.exists(audio_file):
        raise FileNotFoundError("Missing audio.wav")
        
    out_path = os.path.join(project_dir, "alignment.json")
    
    if log_cb: log_cb("Running Whisper Timestamped alignment...")
    
    # Simulate Whisper for now, or dynamically import
    orchestrator.load_model("whisper", lambda: None, required_ram_gb=1.5)
    
    try:
        import whisper_timestamped as whisper
        audio = whisper.load_audio(audio_file)
        model_name = "tiny" if config.get("pipeline", {}).get("preview_mode") else "base"
        model = whisper.load_model(model_name)
        result = whisper.transcribe(model, audio, language="en")
        
        words = []
        for segment in result["segments"]:
            for word in segment["words"]:
                words.append({
                    "word": word["text"],
                    "start": word["start"],
                    "end": word["end"]
                })
        
        with open(out_path, "w") as f:
            json.dump({"words": words}, f, indent=2)
            
    except ImportError:
        if log_cb: log_cb("whisper-timestamped not found. Using dummy alignment.", "warn")
        with open(out_path, "w") as f:
            json.dump({"words": [{"word": "dummy", "start": 0.0, "end": 2.0}]}, f)
            
    if log_cb: log_cb(f"Whisper alignment saved to {out_path}")
    return True
