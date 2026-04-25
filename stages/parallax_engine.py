import os
import json
import subprocess

def run(project_dir: str, config: dict, log_cb=None):
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
    
    if log_cb: log_cb(f"Generating video scenes ({w}x{h}) using {motion_engine} engine...")
    
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
                
                # Trim to exact duration
                subprocess.run(["ffmpeg", "-y", "-i", raw_out, "-t", str(duration), "-c", "copy", out_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(raw_out):
                    os.remove(raw_out)
                continue
            except Exception as e:
                if log_cb: log_cb(f"Warning: Cloud video generation failed for {sid}: {e}. Falling back to 2.5D parallax.")

        frames = int(duration * fps)
        
        if os.path.exists(fg_img):
            filter_complex = (
                f"[0:v]scale=w='iw*(1 + 0.15*n/{frames})':h='ih*(1 + 0.15*n/{frames})':eval=frame,"
                f"crop={w}:{h}:'(iw-ow)/2':'(ih-oh)/2'[bg];"
                f"[1:v]scale=w='iw*(1 + 0.25*n/{frames})':h='ih*(1 + 0.25*n/{frames})':eval=frame,"
                f"crop={w}:{h}:'(iw-ow)/2':'(ih-oh)/2'[fg];"
                f"[bg][fg]overlay=x=0:y=0:format=rgb,format=yuv420p[rawv]"
            )
            inputs = ["-loop", "1", "-i", bg_img, "-loop", "1", "-i", fg_img]
        else:
            filter_complex = (
                f"[0:v]scale=w='iw*(1 + 0.15*n/{frames})':h='ih*(1 + 0.15*n/{frames})':eval=frame,"
                f"crop={w}:{h}:'(iw-ow)/2':'(ih-oh)/2',format=yuv420p[rawv]"
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

