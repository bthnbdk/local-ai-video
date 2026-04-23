import os
import json
from backends.image import flux_backend
from core.memory_orchestrator import orchestrator

def run(project_dir: str, config: dict, log_cb=None):
    prompts_dir = os.path.join(project_dir, "prompts")
    style_file = os.path.join(project_dir, "style.json")
    img_dir = os.path.join(project_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    
    with open(style_file) as f: style = json.load(f)
    base_seed = style.get("seed", 42)
    preview = config.get("pipeline", {}).get("preview_mode", False)
    
    img_backend = config.get("image", {}).get("backend", "auto")
    
    if img_backend == "imagerouter":
        if log_cb: log_cb("Using Cloud API (ImageRouter) for images. Bypassing local VRAM checks.")
        from backends.image.imagerouter_backend import generate_images_batch
        
        # Collect prompts
        if not os.path.exists(prompts_dir):
            raise FileNotFoundError("Missing prompts directory")
            
        prompts = []
        for p_file in sorted(os.listdir(prompts_dir)):
            if not p_file.endswith(".json"): continue
            with open(os.path.join(prompts_dir, p_file)) as f:
                prompts.append(json.load(f))
                
        # Generate via cloud
        success = generate_images_batch(prompts, config, img_dir, log_cb)
        if success and log_cb:
            log_cb("Cloud image generation complete.")
        return success
    
    # Dynamic RAM Check & Wait (Local)
    import time
    import psutil
    
    avail = orchestrator.get_available_ram_gb()
    if avail < 4.0:
        if log_cb: log_cb(f"Low RAM detected ({avail:.2f}GB). Waiting for OS to reclaim memory...")
        for _ in range(5):
            time.sleep(1)
            avail = orchestrator.get_available_ram_gb()
            if avail >= 4.0:
                break
        if avail < 4.0:
            if log_cb: log_cb(f"RAM still low after waiting ({avail:.2f}GB). Proceeding anyway...")
            
    if preview or avail < 8.0:
        if log_cb: log_cb("Using SD1.5/Fallback backend mode.")
        req_ram = 4.0
    else:
        if log_cb: log_cb("Using FLUX backend (mflux).")
        req_ram = 8.0
        
    # Strictly unload any heavyweight models like LLMs or TTS before Flux init
    orchestrator.unload_model()
    
    def load_flux():
        flux_backend.init_model(log_cb)
        
    orchestrator.load_model("image_gen", load_flux, required_ram_gb=req_ram)
    
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
        flux_backend.generate_image(p_data["prompt"], p_data.get("negative_prompt", ""), base_seed + sid, out_img, preview)
        
    if log_cb: log_cb("Image generation complete. Purging Flux objects and VRAM...")
    
    # VRAM STRICT HYGIENE (Delete pointers + mlx.metal.clear_cache)
    flux_backend.cleanup()
    orchestrator.unload_model()
    
    return True
