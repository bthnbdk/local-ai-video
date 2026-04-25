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
            
            # Smart Fit / Crop to target Aspect Ratio
            target_ar = w / h
            img_ar = base_w / base_h
            if img_ar > target_ar + 0.01:
                # Image is wider -> match height, crop width
                scale_factor = h / base_h
            elif img_ar < target_ar - 0.01:
                # Image is taller -> match width, crop height
                scale_factor = w / base_w
            else:
                scale_factor = w / base_w
                
            fit_w = int(base_w * scale_factor)
            fit_h = int(base_h * scale_factor)
            
            x_offset = (w - fit_w) // 2
            y_offset = (h - fit_h) // 2
            
            bg_clip.set_size(width=fit_w, height=fit_h)
            
            import random
            is_2d = False
            if motion_engine == "plain_2d":
                is_2d = True
            elif motion_engine == "mixed":
                is_2d = random.choice([True, False])
                
            if is_2d:
                effect_style = config.get("pipeline", {}).get("2d_effect_style", "mixed")
                if effect_style == "mixed":
                    effect_style = random.choice(["zoom_in", "zoom_out", "pan_left", "pan_right"])
                
                # Apply base centering first
                bg_clip.set_position((x_offset, y_offset))

                if effect_style == "zoom_in":
                    bg_clip.add_effect(vfx.ZoomIn(duration=duration, from_scale=1.0, to_scale=1.1))
                elif effect_style == "zoom_out":
                    bg_clip.add_effect(vfx.ZoomOut(duration=duration, from_scale=1.1, to_scale=1.0))
                elif effect_style == "pan_left":
                    # For pan left, we move the image from right to left or focus position
                    bg_clip.add_effect(vfx.KenBurns(start_scale=1.1, end_scale=1.1, start_position=(0, 0), end_position=(int(fit_w*0.05), 0)))
                elif effect_style == "pan_right":
                    bg_clip.add_effect(vfx.KenBurns(start_scale=1.1, end_scale=1.1, start_position=(int(fit_w*0.05), 0), end_position=(0, 0)))
                
                clips = [bg_clip]
                
            else:
                # blur bg slightly to separate it from fg
                bg_clip.add_effect(vfx.Blur(intensity=2.0))
                
                clips = [bg_clip]
                
                if os.path.exists(fg_img):
                    cx_orig, cy_orig = get_centroid(fg_img)
                    cx = int(cx_orig * scale_factor) + x_offset
                    cy = int(cy_orig * scale_factor) + y_offset
                else:
                    cx, cy = w // 2, h // 2
                    
                def create_scale(max_zoom):
                    return lambda t: 1.0 + max_zoom * (t / duration)
                    
                def create_pos(max_zoom, _cx, _cy, _xoff, _yoff):
                    # Based on cx, cy anchor and base offsets
                    return lambda t, _c=_cx, _cy2=_cy, zoom=max_zoom: (
                        int(_xoff - (_c - _xoff) * (zoom * (t / duration))),
                        int(_yoff - (_cy2 - _yoff) * (zoom * (t / duration)))
                    )

                bg_clip.set_scale(create_scale(0.10))
                bg_clip.set_position(create_pos(0.10, cx, cy, x_offset, y_offset))
                
                if os.path.exists(fg_img):
                    fg_clip = ImageClip(fg_img, duration=duration)
                    fg_clip.set_size(width=fit_w, height=fit_h)
                    fg_clip.set_scale(create_scale(0.20))
                    fg_clip.set_position(create_pos(0.20, cx, cy, x_offset, y_offset))
                    clips.append(fg_clip)
                    
            # Apply Micro Motions
            micro_motion = config.get("pipeline", {}).get("micro_motion", "none")
            if micro_motion == "mixed":
                micro_motion = random.choice(["shake", "pulse", "blur", "none"])
                
            for c in clips:
                if micro_motion == "shake":
                    # We wrap the position function dynamically
                    # MovieLite doesn't always expose .position, so we'll wrap a default
                    try:
                        orig = c.pos if hasattr(c, 'pos') else (x_offset, y_offset)
                    except:
                        orig = (x_offset, y_offset)
                        
                    def create_shake(start_pos):
                        return lambda t: (
                            (start_pos(t)[0] if callable(start_pos) else start_pos[0]) + int(np.random.uniform(-2, 2)),
                            (start_pos(t)[1] if callable(start_pos) else start_pos[1]) + int(np.random.uniform(-2, 2))
                        )
                    c.set_position(create_shake(orig))
                    
                elif micro_motion == "pulse":
                    try:
                        orig_s = c.scale if hasattr(c, 'scale') else 1.0
                    except:
                        orig_s = 1.0
                        
                    def create_pulse(start_scale):
                        return lambda t: (start_scale(t) if callable(start_scale) else start_scale) * (1.0 + 0.02 * np.sin(np.pi * t))
                    c.set_scale(create_pulse(orig_s))
                    
                elif micro_motion == "blur":
                    c.add_effect(vfx.Blur(intensity=lambda t: 0.5 + 1.0 * np.abs(np.sin(t))))
            
            if log_cb: log_cb(f"Rendering scene {sid} ({duration}s)")
            writer = VideoWriter(out_path, fps=fps, size=(w, h), duration=duration)
            writer.add_clips(clips)
            writer.write()
        except Exception as e:
            if log_cb: log_cb(f"Warning: movielite failed for scene {sid}: {e}")
            with open(out_path, "w") as empty: empty.write("")
            
    return True

