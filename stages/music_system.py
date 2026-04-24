import os
import json
import random
import shutil
import numpy as np
import soundfile as sf
# Removed audiocraft and memory_orchestrator dependencies

def compute_ducking_envelope(vo_data, sample_rate, target_length):
    # VO is typically mono; if stereo convert to mono
    if len(vo_data.shape) > 1:
        vo_data = np.mean(vo_data, axis=1)
        
    power = np.abs(vo_data)
    block_size = int(sample_rate * 0.05) # 50ms blocks
    num_blocks = len(power) // block_size
    
    if num_blocks == 0:
        return np.ones(target_length)
        
    blocked = power[:num_blocks * block_size].reshape(num_blocks, block_size)
    block_env = np.max(blocked, axis=1)
    
    env_smoothed = np.zeros(num_blocks)
    attack = 0.85 # Fast attack
    release = 0.98 # Slow swell recovery
    curr = 0.0
    for i in range(num_blocks):
        target = block_env[i]
        if target > curr:
            curr = attack * curr + (1 - attack) * target
        else:
            curr = release * curr + (1 - release) * target
        env_smoothed[i] = curr
        
    max_val = np.max(env_smoothed)
    if max_val > 0.01:
        env_smoothed /= max_val
        
    x_old = np.linspace(0, 1, num_blocks)
    x_new = np.linspace(0, 1, target_length)
    interp_env = np.interp(x_new, x_old, env_smoothed)
    
    # 0.15 represents ~ -16.5dB (ducking), 0.85 is normal volume
    gain = 0.85 - (interp_env * 0.70)
    return gain

def run(project_dir: str, config: dict, log_cb=None):
    out_path = os.path.join(project_dir, "music.wav")
    
    mode = config.get("pipeline", {}).get("music_mode", "generated")
    music_file = config.get("pipeline", {}).get("music_file", "")
    music_mood = config.get("pipeline", {}).get("music_genre", "cinematic").lower()
    
    script_path = os.path.join(project_dir, "script.json")
    timing_path = os.path.join(project_dir, "timing.json")
    
    if not os.path.exists(script_path) or not os.path.exists(timing_path):
        if log_cb: log_cb("Missing script or timing data. Generating blank audio.", "warn")
        import wave, struct
        with wave.open(out_path, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            data = struct.pack('<h', 0) * (16000 * 2)
            wav.writeframesraw(data)
        return True
        
    with open(script_path) as f: script_data = json.load(f)
    with open(timing_path) as f: timing_data = json.load(f)
    
    scenes = script_data.get("scenes", [])
    timings = timing_data.get("scenes", [])
    
    if not scenes or not timings or len(scenes) != len(timings):
        if log_cb: log_cb("Mismatch in scenes/timings. Using empty music.", "error")
        return True
    
    total_duration = timings[-1]["end"] - timings[0]["start"]
    sample_rate = 32000
    
    final_audio = None
    
    selected_music_file = ""
    
    if mode == "local" and os.path.exists(music_file):
        if log_cb: log_cb(f"BYOA Bypass: Loading custom audio {music_file}")
        selected_music_file = music_file
    else:
        # Folder-based logic
        mood_folder = os.path.join("assets", "music", music_mood)
        os.makedirs(mood_folder, exist_ok=True)
        
        valid_files = [f for f in os.listdir(mood_folder) if f.lower().endswith(('.mp3', '.wav'))]
        if not valid_files:
            if log_cb: log_cb(f"No music found in folder {mood_folder}. Skipping music track.", "warn")
            import wave, struct
            with wave.open(out_path, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                data = struct.pack('<h', 0) * (16000 * 2)
                wav.writeframesraw(data)
            return True
            
        chosen_file = random.choice(valid_files)
        selected_music_file = os.path.join(mood_folder, chosen_file)
        if log_cb: log_cb(f"Selected background music: {chosen_file} from {music_mood}")
        
    try:
        custom_audio, custom_sr = sf.read(selected_music_file)
        if len(custom_audio.shape) > 1:
            custom_audio = np.mean(custom_audio, axis=1)
            
        sample_rate = custom_sr
        req_samples = int(total_duration * sample_rate)
        
        if len(custom_audio) < req_samples:
            # Loop it cleanly
            repeats = (req_samples // len(custom_audio)) + 1
            final_audio = np.tile(custom_audio, repeats)[:req_samples]
        else:
            # Trim it exactly
            final_audio = custom_audio[:req_samples]
            
        # Audio ducking
        vo_path = os.path.join(project_dir, "audio.wav")
        if os.path.exists(vo_path):
            if log_cb: log_cb("Applying dynamic audio ducking (analyzing voiceover amplitude)...")
            vo_data, vo_sr = sf.read(vo_path)
            duck_envelope = compute_ducking_envelope(vo_data, vo_sr, len(final_audio))
            final_audio = final_audio * duck_envelope
        else:
            if log_cb: log_cb("audio.wav not found. Applying static mixing volume.")
            final_audio = final_audio * 0.2
            
        final_audio = np.clip(final_audio, -1.0, 1.0)
        sf.write(out_path, final_audio, sample_rate)
        
    except Exception as e:
        if log_cb: log_cb(f"Audio processing failed: {e}. Falling back to empty track.", "error")
        import wave, struct
        with wave.open(out_path, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            data = struct.pack('<h', 0) * (16000 * 2)
            wav.writeframesraw(data)
        return True
    
    if log_cb: log_cb(f"Background music processed successfully.")
    return True
