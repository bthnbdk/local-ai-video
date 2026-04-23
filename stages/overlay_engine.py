import os
import shutil

def run(project_dir: str, config: dict, log_cb=None):
    scenes_dir = os.path.join(project_dir, "scenes")
    overlaid_dir = os.path.join(project_dir, "overlaid")
    os.makedirs(overlaid_dir, exist_ok=True)
    
    if log_cb: log_cb("Applying text overlays...")
    
    for f in os.listdir(scenes_dir):
        if f.endswith(".mp4"):
            shutil.copy(os.path.join(scenes_dir, f), os.path.join(overlaid_dir, f))
            
    return True
