import os
import shutil

def run(project_dir: str, config: dict, log_cb=None):
    enabled = config.get("pipeline", {}).get("depth_enabled", False)
    
    if not enabled:
        if log_cb: log_cb("Depth estimation disabled. Skipping.")
        return True
        
    up_dir = os.path.join(project_dir, "upscaled")
    depth_dir = os.path.join(project_dir, "depth")
    os.makedirs(depth_dir, exist_ok=True)
    
    if log_cb: log_cb("Computing depth maps (simulated MiDaS)...")
    
    for f in os.listdir(up_dir):
        if f.endswith(".png"):
            shutil.copy(os.path.join(up_dir, f), os.path.join(depth_dir, f))
            
    return True
