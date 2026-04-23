import os
import json
from backends.image.flux_backend import generate_image as flux_gen
from core.memory_orchestrator import orchestrator

def run(project_dir: str, config: dict, log_cb=None):
    prompts_dir = os.path.join(project_dir, "prompts")
    style_file = os.path.join(project_dir, "style.json")
    img_dir = os.path.join(project_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    
    with open(style_file) as f: style = json.load(f)
    base_seed = style.get("seed", 42)
    
    # RAM Check
    avail = orchestrator.get_available_ram_gb()
    preview = config.get("pipeline", {}).get("preview_mode", False)
    
    if preview or avail < 8.0:
        if log_cb: log_cb("Using SD1.5 backend fallback.")
        req_ram = 4.0
    else:
        if log_cb: log_cb("Using FLUX/SDXL backend.")
        req_ram = 8.0
        
    orchestrator.load_model("image_gen", lambda: None, required_ram_gb=req_ram)
    
    if not os.path.exists(prompts_dir):
        raise FileNotFoundError("Missing prompts directory")
        
    for p_file in sorted(os.listdir(prompts_dir)):
        if not p_file.endswith(".json"): continue
        with open(os.path.join(prompts_dir, p_file)) as f:
            p_data = json.load(f)
            
        sid = p_data["scene_id"]
        out_img = os.path.join(img_dir, f"scene_{sid}.png")
        
        if log_cb: log_cb(f"Generating image for scene {sid}...")
        
        # Generation call
        flux_gen(p_data["prompt"], p_data["negative_prompt"], base_seed + sid, out_img, preview)
        
    if log_cb: log_cb("Image generation complete.")
    return True
