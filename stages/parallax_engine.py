import os
import json
import subprocess

def run(project_dir: str, config: dict, log_cb=None):
    up_dir = os.path.join(project_dir, "upscaled")
    mask_dir = os.path.join(project_dir, "masks")
    scenes_dir = os.path.join(project_dir, "scenes")
    timing_file = os.path.join(project_dir, "timing.json")
    os.makedirs(scenes_dir, exist_ok=True)
    
    with open(timing_file) as f: timing = json.load(f)
    
    ar = config.get("pipeline", {}).get("aspect_ratio", "16:9")
    if ar == "16:9":
        w, h = 1024, 576
    elif ar == "9:16":
        w, h = 576, 1024
    else:
        w, h = 1024, 1024
        
    if log_cb: log_cb(f"Generating 2.5D parallax video scenes ({w}x{h})...")
    
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
            
        frames = int(duration * fps)
        
        # We use a complex filter to scale the sequence frame by frame
        # to avoid zoompan destroying the alpha channel, and apply to both BG and FG
        
        # Background: zoom from 1.0 to 1.05
        # Foreground: zoom from 1.0 to 1.15
        
        # Scale equation: target_width * (1 + (end_zoom - 1) * (n / frames))
        # We need to crop it back to w, h
        
        if os.path.exists(fg_img):
            filter_complex = (
                f"[0:v]zoompan=z='1+0.05*(on/{frames})':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':d={frames}:s={w}x{h},format=rgb24[bg];"
                f"[1:v]split[fg_rgb][fg_alpha_base];"
                f"[fg_alpha_base]alphaextract[fg_alpha];"
                f"[fg_rgb]zoompan=z='1+0.15*(on/{frames})':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':d={frames}:s={w}x{h}[fg_c];"
                f"[fg_alpha]zoompan=z='1+0.15*(on/{frames})':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':d={frames}:s={w}x{h}[fg_a];"
                f"[fg_c][fg_a]alphamerge[fg_merged];"
                f"[bg][fg_merged]overlay=x=0:y=0:format=rgb,format=yuv420p[rawv]"
            )
            inputs = ["-loop", "1", "-i", bg_img, "-loop", "1", "-i", fg_img]
        else:
            filter_complex = (
                f"[0:v]zoompan=z='1+0.05*(on/{frames})':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':d={frames}:s={w}x{h},format=yuv420p[rawv]"
            )
            inputs = ["-loop", "1", "-i", bg_img]
            
        fade_filter = ""
        if transition == "crossfade" and duration > 1.0:
            fade_filter = f";[rawv]fade=t=in:st=0:d=0.3,fade=t=out:st={max(0, duration-0.5)}:d=0.5[v]"
        elif transition == "dip_to_black" and duration > 1.0:
            fade_filter = f";[rawv]fade=t=out:st={max(0, duration-0.5)}:d=0.5[v]"
        else:
            fade_filter = f";[rawv]copy[v]"
            
        filter_complex += fade_filter
            
        cmd = [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-t", str(duration), "-r", str(fps), "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path
        ]
        
        if log_cb: log_cb(f"Rendering scene {sid} ({duration}s)")
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            if log_cb: log_cb(f"Warning: ffmpeg failed for scene {sid}: {e}")
            with open(out_path, "w") as empty: empty.write("")
            
    return True
