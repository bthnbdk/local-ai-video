import os
import json

def run(project_dir: str, config: dict, log_cb=None):
    script_file = os.path.join(project_dir, "script.json")
    align_file = os.path.join(project_dir, "alignment.json")
    out_path = os.path.join(project_dir, "timing.json")
    
    if not os.path.exists(script_file) or not os.path.exists(align_file):
        raise FileNotFoundError("Missing script.json or alignment.json")
        
    with open(script_file) as f: script = json.load(f)
    with open(align_file) as f: align = json.load(f)
    
    if log_cb: log_cb("Computing scene timings...")
    
    # Fuzzy match logic simplified for robust execution here
    # In a full run, we map word counts to scenes evenly as a fallback
    words = align.get("words", [])
    total_words = len(words)
    scenes = script.get("scenes", [])
    
    timings = []
    current_word_idx = 0
    words_per_scene = total_words // len(scenes) if scenes else 1
    
    for i, _ in enumerate(scenes):
        start_idx = current_word_idx
        end_idx = min(start_idx + words_per_scene, total_words - 1)
        
        start_t = words[start_idx]["start"] if start_idx < total_words else 0.0
        end_t = words[end_idx]["end"] if end_idx < total_words else start_t + 2.0
        end_t += 0.3 # Buffer
        
        timings.append({
            "scene_id": i,
            "start": start_t,
            "end": end_t
        })
        current_word_idx = end_idx + 1
        
    with open(out_path, "w") as f:
        json.dump({"scenes": timings}, f, indent=2)
        
    if log_cb: log_cb("Timing computation complete.")
    return True
