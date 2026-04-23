import os
import json
import numpy as np
import soundfile as sf
from core.memory_orchestrator import orchestrator

EMOTION_MAP = {
    "neutral": "ambient, calm, slow tempo, atmospheric synth, subtle piano",
    "joyful": "upbeat, acoustic guitar, light percussion, happy, bright, 120 bpm",
    "tense": "dark, low strings, slow heartbeat drum, eerie synth, suspenseful",
    "melancholic": "sad piano, solo cello, slow tempo, reverb, emotional, heartfelt",
    "awe": "orchestral swell, choir, french horns, epic, cinematic, wide sound",
    "urgency": "fast tempo, electronic pulses, driving bassline, tense action, 140 bpm"
}

def get_detailed_prompt(emotion):
    return EMOTION_MAP.get(emotion, EMOTION_MAP["neutral"])

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
    # When env is 1.0 -> gain drops to ~0.15 (ducking limits)
    # When env is 0.0 -> gain swells to 0.85 
    gain = 0.85 - (interp_env * 0.70)
    return gain

def run(project_dir: str, config: dict, log_cb=None):
    out_path = os.path.join(project_dir, "music.wav")
    
    # Default to generated for our dynamic soundtrack
    mode = config.get("pipeline", {}).get("music_mode", "generated")
    music_file = config.get("pipeline", {}).get("music_file", "")
    music_genre = config.get("pipeline", {}).get("music_genre", "")
    
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
    
    # Total runtime analysis
    total_duration = timings[-1]["end"] - timings[0]["start"]
    sample_rate = 32000
    
    final_audio = None
    
    if mode == "local" and os.path.exists(music_file):
        if log_cb: log_cb(f"BYOA Bypass: Loading custom audio {music_file}")
        try:
            custom_audio, custom_sr = sf.read(music_file)
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
        except Exception as e:
            if log_cb: log_cb(f"BYOA failed: {e}. Falling back to empty track.", "error")
            import wave, struct
            with wave.open(out_path, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                data = struct.pack('<h', 0) * (16000 * 2)
                wav.writeframesraw(data)
            return True
    else:
        # 1. MOOD BLOCK CHUNKING
        mood_blocks = []
        current_emotion = scenes[0].get("emotion", "neutral")
        block_start = timings[0]["start"]
        
        for i in range(1, len(scenes)):
            emo = scenes[i].get("emotion", "neutral")
            if emo != current_emotion:
                block_end = timings[i-1]["end"]
                duration = block_end - block_start
                mood_blocks.append({
                    "emotion": current_emotion,
                    "duration": duration + 2.0  # 2s buffer reserved for audio transition
                })
                current_emotion = emo
                block_start = timings[i]["start"]
                
        # Final block
        block_end = timings[-1]["end"]
        mood_blocks.append({
            "emotion": current_emotion,
            "duration": (block_end - block_start) + 2.0
        })
        
        if log_cb: log_cb(f"Chunked narrative into {len(mood_blocks)} continuous Mood Blocks.")

        # 3. STRICT MEMORY HYGIENE
        music_model_instance = None
        try:
            from audiocraft.models import MusicGen
            def load_musicgen():
                nonlocal music_model_instance
                music_model_instance = MusicGen.get_pretrained('small')
                
            orchestrator.load_model("audiocraft_musicgen", load_musicgen, required_ram_gb=2.0)
        except ImportError:
            if log_cb: log_cb("audiocraft missing. Simulating dynamic emotional music.", "warn")

        block_audios = []
        
        # 2. EMOTION TRANSLATION + GLOBAL GENRE
        for idx, block in enumerate(mood_blocks):
            prompt = get_detailed_prompt(block["emotion"])
            if music_genre:
                prompt = f"{music_genre}, {prompt}"
                
            duration = block["duration"]
            if log_cb: log_cb(f"Gen Block {idx+1}/{len(mood_blocks)}: {prompt[:50]}..., {duration:.1f}s")
            
            if music_model_instance is not None:
                music_model_instance.set_generation_params(duration=duration)
                wav = music_model_instance.generate([prompt])
                audio_data = wav[0].cpu().numpy()[0] # [1, c, t] -> Mono flattened array
                block_audios.append(audio_data)
            else:
                # Simulate distinctive tonal emotional blocks with varying harmonics
                t = np.linspace(0, duration, int(sample_rate * duration), False)
                base_freq = 200 + (len(block["emotion"]) * 10) + (idx * 20)
                noise = np.random.randn(len(t)) * 0.02
                audio_data = np.sin(2 * np.pi * base_freq * t) * 0.1 + noise
                block_audios.append(audio_data)

        # STRICT MEMORY HYGIENE
        if music_model_instance is not None:
            del music_model_instance
        orchestrator.unload_model()
        
        # 4. ADVANCED NON-LINEAR CONSTANT-POWER CROSSFADING
        if log_cb: log_cb("Applying constant-power non-linear crossfading...")
        fade_duration = 2.0
        fade_samples = int(fade_duration * sample_rate)
        
        final_audio = block_audios[0]
        
        for i in range(1, len(block_audios)):
            next_audio = block_audios[i]
            len_final = len(final_audio)
            len_next = len(next_audio)
            
            overlap_start = max(0, len_final - fade_samples)
            actual_fade_samples = len_final - overlap_start
            
            # Constant power (Non-linear sine/cosine) interpolation
            t_fade = np.linspace(0, np.pi/2, actual_fade_samples)
            fade_out = np.cos(t_fade)
            fade_in = np.sin(t_fade)
            
            final_audio[overlap_start:] *= fade_out
            
            next_part = next_audio.copy()
            if len_next >= actual_fade_samples:
                next_part[:actual_fade_samples] *= fade_in
            else:
                next_part *= fade_in[:len_next]
                
            padded_size = overlap_start + len_next
            padded_final = np.zeros(padded_size)
            padded_final[:len_final] = final_audio
            padded_final[overlap_start:overlap_start + len_next] += next_part
            
            final_audio = padded_final

    # 5. ADVANCED DYNAMIC AUDIO DUCKING
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
    
    if log_cb: log_cb(f"Dynamic emotion-driven soundtrack fully mastered.")
    return True
