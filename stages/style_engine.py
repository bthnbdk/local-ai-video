import os
import json
import random

def run(project_dir: str, config: dict, log_cb=None):
    style_conf = config.get("style", {})
    mode = style_conf.get("mode", "library")
    out_path = os.path.join(project_dir, "style.json")
    
    if log_cb: log_cb(f"Processing style mode: {mode}")
    
    style_data = {
        "style_name": "default",
        "base_prompt": "cinematic, high quality",
        "color_palette": "muted",
        "lighting": "soft",
        "camera": "wide",
        "texture": "grain",
        "negative_prompt": "ugly, watermark"
    }

    if mode == "library":
        name = style_conf.get("name", "cinematic_dark")
        lib_path = "templates/prompts/styles.json"
        
        # Default mapping in case of missing items
        style_data = {
            "style_name": name,
            "base_prompt": "",
            "color_palette": "",
            "lighting": "",
            "camera": "",
            "texture": "",
            "negative_prompt": "ugly, watermark"
        }
        
        if os.path.exists(lib_path):
            with open(lib_path) as f:
                lib = json.load(f)
                for s in lib:
                    if s["id"] == name:
                        style_data["base_prompt"] = s.get("positive_suffix", "")
                        style_data["negative_prompt"] = s.get("negative_suffix", "ugly, watermark")
                        break

    # Add Text in Image constraints
    text_control = config.get("pipeline", {}).get("text_control", "allow")
    if text_control == "strict_no_text":
        style_data["base_prompt"] += ", no text, no writing, no watermark, no typography, blank surfaces"
        style_data["negative_prompt"] += ", text, watermark, signature, font, writing, typography"
                        
    # Seed lock for consistency
    style_data["seed"] = random.randint(0, 10000)
    
    with open(out_path, "w") as f:
        json.dump(style_data, f, indent=2)
        
    if log_cb: log_cb("Style engine finished.")
    return True
