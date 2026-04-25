import os
import json

def run(project_dir: str, config: dict, log_cb=None):
    from movielite import VideoClip, AudioClip, TextClip, VideoWriter, vtx
    from pictex import Canvas, Shadow

    out_dir = os.path.join(project_dir, "final")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "output.mp4")
    
    fps = config.get("pipeline", {}).get("fps", 30)
    transition = config.get("pipeline", {}).get("transition", "crossfade")
    subtitles_enabled = config.get("pipeline", {}).get("subtitles", False)
    
    if log_cb: log_cb(f"Assembling final video ({fps} FPS, {transition} transitions) using movielite...")
    
    scenes_dir = os.path.join(project_dir, "scenes")
    if not os.path.exists(scenes_dir):
        if log_cb: log_cb("No scenes found.", "error")
        return False
        
    scene_files = sorted([os.path.join(scenes_dir, f) for f in os.listdir(scenes_dir) if f.endswith(".mp4")])
    if not scene_files: return False
    
    valid_scenes = []
    for sf in scene_files:
        if os.path.exists(sf) and os.path.getsize(sf) > 0:
            valid_scenes.append(sf)
        else:
            if log_cb: log_cb(f"CRITICAL ERROR: Scene video {sf} is missing or 0 bytes. Halting.", "error")
            return False
            
    scene_files = valid_scenes
    
    clips = []
    current_time = 0.0
    for i, sf in enumerate(scene_files):
        try:
            clip = VideoClip(sf, start=current_time)
            if transition == "crossfade" and i > 0:
                overlap = min(0.5, clip.duration / 2)
                clip.set_start(current_time - overlap)
                prev_clip = clips[-1]
                prev_clip.add_transition(clip, vtx.CrossFade(duration=overlap))
                current_time += (clip.duration - overlap)
            else:
                current_time += clip.duration
            clips.append(clip)
        except Exception as e:
            if log_cb: log_cb(f"Error loading {sf}: {e}", "error")
            return False

    final_clips = list(clips)

    audio_path = os.path.join(project_dir, "mixed_audio.wav")
    if os.path.exists(audio_path):
        final_clips.append(AudioClip(audio_path, start=0))
    else:
        vo_path = os.path.join(project_dir, "audio.wav")
        bg_path = os.path.join(project_dir, "music.wav")
        if os.path.exists(vo_path):
            final_clips.append(AudioClip(vo_path, start=0, volume=1.0))
        if os.path.exists(bg_path):
            final_clips.append(AudioClip(bg_path, start=0, volume=1.0))

    if subtitles_enabled:
        alignment_file = os.path.join(project_dir, "alignment.json")
        if os.path.exists(alignment_file):
            try:
                with open(alignment_file) as f:
                    words_data = json.load(f)
                
                segments = words_data.get("segments", []) if isinstance(words_data, dict) else words_data

                def resolve_groups(segment):
                    segment_words = segment.get("words")
                    groups = []
                    if isinstance(segment_words, list) and len(segment_words) > 0 and isinstance(segment_words[0], dict):
                        group = []
                        for i, w in enumerate(segment_words):
                            group.append(w)
                            if len(group) >= 3 or i == len(segment_words) - 1:
                                start = float(group[0].get("start", 0))
                                end = float(group[-1].get("end", start + 1.0))
                                text = " ".join([wd.get("word", "").strip() for wd in group])
                                if text: groups.append((start, end, text))
                                group = []
                    else:
                        if "start" in segment and "end" in segment:
                            text = segment.get("text", segment.get("word", "")).strip()
                            if text:
                                groups.append((float(segment["start"]), float(segment["end"]), text))
                    return groups

                ar = config.get("pipeline", {}).get("aspect_ratio", "16:9")
                base_w = 1024 if ar != "9:16" else 576
                font_size = int(base_w * 0.05)
                
                canvas = (
                    Canvas()
                    .font_family("Arial")
                    .font_weight("bold")
                    .font_size(font_size)
                    .color("yellow")
                    .text_shadows(Shadow(offset=(2, 2), blur_radius=2, color="black"))
                    .text_shadows(Shadow(offset=(-2, -2), blur_radius=2, color="black"))
                    .background_color("transparent")
                )

                for segment in segments:
                    if not isinstance(segment, dict): continue
                    groups = resolve_groups(segment)
                    for start, end, text in groups:
                        duration = end - start
                        if duration <= 0: continue
                        t_clip = TextClip(text, start=start, duration=duration, canvas=canvas)
                        
                        def create_pos_func(tw, th):
                            return lambda t, mw=clips[0].size[0], mh=clips[0].size[1]: (mw // 2 - tw // 2, int(mh * 0.85 - th//2))
                            
                        t_clip.set_position(create_pos_func(t_clip.size[0], t_clip.size[1]))
                        final_clips.append(t_clip)
            except Exception as e:
                if log_cb: log_cb(f"Warning: Failed to process subtitles: {e}")

    # Calculate total duration
    total_duration = max([c.end for c in final_clips if hasattr(c, 'end')] + [0])
    
    if len(clips) > 0:
        base_size = clips[0].size
        try:
            writer = VideoWriter(out_path, fps=fps, size=base_size, duration=total_duration)
            writer.add_clips(final_clips)
            writer.write()
        except Exception as e:
            if log_cb: log_cb(f"Movielite rendering failed: {e}", "error")
            return False
    else:
        return False

    if log_cb: log_cb(f"Final video rendered to {out_path}")
    return True
