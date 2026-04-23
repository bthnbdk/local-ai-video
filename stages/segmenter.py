import os
import shutil

def run(project_dir: str, config: dict, log_cb=None):
    up_dir = os.path.join(project_dir, "upscaled")
    mask_dir = os.path.join(project_dir, "masks")
    os.makedirs(mask_dir, exist_ok=True)
    
    if log_cb: log_cb("Segmenting images (simulated rembg)...")
    
    for f in os.listdir(up_dir):
        if f.endswith(".png"):
            # Dummy logic: copy original as mask for simplicity since we don't execute
            shutil.copy(os.path.join(up_dir, f), os.path.join(mask_dir, f))
            
    return True
