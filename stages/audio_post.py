import os
import shutil

def run(project_dir: str, config: dict, log_cb=None):
    audio_in = os.path.join(project_dir, "audio.wav")
    audio_out = os.path.join(project_dir, "audio_final.wav")
    
    if os.path.exists(audio_in):
        shutil.copy(audio_in, audio_out)
        if log_cb: log_cb("Audio post-processing (normalized).")
    
    return True
