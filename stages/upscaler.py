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
        
    upscale_backend = config.get("image", {}).get("upscale_backend", "local")
    if upscale_backend == "imagerouter":
        if log_cb: log_cb("Using Cloud API (ImageRouter) for Upscaling. Bypassing local VRAM.")
        from backends.image.imagerouter_backend import upscale_cloud
        for f in os.listdir(img_dir):
            if f.endswith(".png"):
                in_path = os.path.join(img_dir, f)
                out_path = os.path.join(up_dir, f)
                upscale_cloud(in_path, out_path, config, log_cb)
        return True
        
    if log_cb: log_cb("Upscaling images (Local PIL Lanczos)...")
    from PIL import Image
    for f in os.listdir(img_dir):
        if f.endswith(".png"):
            in_path = os.path.join(img_dir, f)
            out_path = os.path.join(up_dir, f)
            try:
                img = Image.open(in_path)
                # target width around 1024 or 2x
                new_width = img.width * 2
                new_height = img.height * 2
                if new_height > 2048:
                    ratio = 2048 / img.height
                    new_height = int(img.height * ratio)
                    new_width = int(img.width * ratio)
                
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                img.save(out_path)
            except Exception as e:
                if log_cb: log_cb(f"Failed to upscale {f}: {e}")
                shutil.copy(in_path, out_path)
            
    return True
