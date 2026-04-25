import os
import json
import subprocess
import numpy as np
from PIL import Image

def get_centroid(image_path):
    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]
    y_coords, x_coords = np.where(alpha > 0)
    if len(x_coords) == 0:
        return img.width // 2, img.height // 2
    
    min_x, max_x = np.min(x_coords), np.max(x_coords)
    min_y, max_y = np.min(y_coords), np.max(y_coords)
    return (min_x + max_x) // 2, (min_y + max_y) // 2

def run(project_dir: str, config: dict, log_cb=None):
    from movielite import ImageClip, VideoWriter, vfx
    up_dir = os.path.join(project_dir, "upscaled")
    mask_dir = os.path.join(project_dir, "masks")
    scenes_dir = os.path.join(project_dir, "scenes")
    timing_file = os.path.join(project_dir, "timing.json")
    script_file = os.path.join(project_dir, "script.json")
    os.makedirs(scenes_dir, exist_ok=True)
    
    with open(timing_file) as f: timing = json.load(f)
    
    script_data = {}
    if os.path.exists(script_file):
        with open(script_file) as f: script_data = json.load(f)
        
    def get_scene_prompt(sid):
        for s in script_data.get("scenes", []):
            if s.get("id") == sid or f"scene_{s.get('id')}" == sid or str(s.get("id")) == str(sid):
                return s.get("visual_prompt", "")
        return ""
    
    ar = config.get("pipeline", {}).get("aspect_ratio", "16:9")
    if ar == "16:9":
        w, h = 1024, 576
    elif ar == "9:16":
        w, h = 576, 1024
    else:
        w, h = 1024, 1024
        
    motion_engine = config.get("pipeline", {}).get("motion_source", "local")
    
    if log_cb: log_cb(f"Generating video scenes ({w}x{h}) using {motion_engine} engine (movielite)...")
    
    fps = config.get("pipeline", {}).get("fps", 30)
    transition = config.get("pipeline", {}).get("transition", "crossfade")
    
    for t in timing.get("scenes", []):
        sid = t["scene_id"]
        duration = t["end"] - t["start"]
        bg_img = os.path.join(up_dir, f"scene_{sid}.png")
        fg_img = os.path.join(mask_dir, f"scene_{sid}.png")
        out_path = os.path.join(scenes_dir, f"scene_{sid}.mp4")
        
        if not os.path.exists(bg_img):
            continue
            
        if motion_engine == "cloud":
            try:
                from backends.video.imagerouter_video_backend import generate_video
                prompt = get_scene_prompt(sid)
                if log_cb: log_cb(f"  -> Cloud AI Video for scene {sid} (prompt: {prompt[:30]}...)")
                
                raw_out = out_path + ".raw.mp4"
                generate_video(prompt, bg_img, raw_out, duration)
                
                subprocess.run(["ffmpeg", "-y", "-i", raw_out, "-t", str(duration), "-c", "copy", out_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(raw_out):
                    os.remove(raw_out)
                continue
            except Exception as e:
                if log_cb: log_cb(f"Warning: Cloud video generation failed for {sid}: {e}. Falling back to 2.5D parallax.")

        try:
            bg_clip = ImageClip(bg_img, duration=duration)
            base_w, base_h = bg_clip.size
            
            # blur bg slightly to separate it from fg
            bg_clip.add_effect(vfx.Blur(intensity=2.0))
            
            clips = [bg_clip]
            
            if os.path.exists(fg_img):
                cx, cy = get_centroid(fg_img)
            else:
                cx, cy = base_w // 2, base_h // 2
                
            def create_scale(max_zoom):
                return lambda t: 1.0 + max_zoom * (t / duration)
                
            def create_pos(max_zoom, _cx, _cy):
                return lambda t, cx=_cx, cy=_cy: (int(cx - cx * (1.0 + max_zoom * (t / duration))), int(cy - cy * (1.0 + max_zoom * (t / duration))))

            bg_clip.set_scale(create_scale(0.10))
            bg_clip.set_position(create_pos(0.10, cx, cy))
            
            if os.path.exists(fg_img):
                fg_clip = ImageClip(fg_img, duration=duration)
                fg_clip.set_scale(create_scale(0.20))
                fg_clip.set_position(create_pos(0.20, cx, cy))
                clips.append(fg_clip)
            
            if log_cb: log_cb(f"Rendering scene {sid} ({duration}s)")
            writer = VideoWriter(out_path, fps=fps, size=(w, h), duration=duration)
            writer.add_clips(clips)
            writer.write()
        except Exception as e:
            if log_cb: log_cb(f"Warning: movielite failed for scene {sid}: {e}")
            with open(out_path, "w") as empty: empty.write("")
            
    return True

