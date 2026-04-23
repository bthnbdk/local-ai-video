import os
import shutil

def run(project_dir: str, config: dict, log_cb=None):
    preview = config.get("pipeline", {}).get("preview_mode", False)
    img_dir = os.path.join(project_dir, "images")
    up_dir = os.path.join(project_dir, "upscaled")
    os.makedirs(up_dir, exist_ok=True)
    
    if preview:
        if log_cb: log_cb("Preview mode: skipping upscale. Copying images.")
        for f in os.listdir(img_dir):
            if f.endswith(".png"):
                shutil.copy(os.path.join(img_dir, f), os.path.join(up_dir, f))
        return True
        
    if log_cb: log_cb("Upscaling images (simulated RealESRGAN)...")
    # Simulate Real-ESRGAN in a real environment
    for f in os.listdir(img_dir):
        if f.endswith(".png"):
            # Dummy copy
            shutil.copy(os.path.join(img_dir, f), os.path.join(up_dir, f))
            
    return True
