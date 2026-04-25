import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, Response, stream_with_context, jsonify
import queue
import json
import threading
from core.pipeline_runner import PipelineRunner
from core.state_manager import StateManager

app = Flask(__name__)
log_queues = {}

def get_projects():
    if not os.path.exists("projects"): os.makedirs("projects")
    return [p for p in os.listdir("projects") if os.path.isdir(os.path.join("projects", p))]

@app.route("/")
def dashboard():
    projects_data = []
    import datetime
    for p in get_projects():
        provider = "Local"
        status = "Unknown"
        created_at = "Unknown Date"
        
        project_path = os.path.join("projects", p)
        try:
            stat = os.stat(project_path)
            created_at = datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M")
        except:
            pass

        sm_path = os.path.join(project_path, "state.json")
        if os.path.exists(sm_path):
            try:
                with open(sm_path) as f:
                    state = json.load(f)
                    if state.get("config", {}).get("llm", {}).get("backend") == "gemini":
                        provider = "Cloud"
                    
                    # Logic to determine status
                    # if there is a status field we use it, otherwise infer
                    if state.get("status"):
                        status = state.get("status")
                    elif state.get("completed_stages") and "final_video" in state.get("completed_stages", []):
                        status = "completed"
                    elif state.get("failed_stages"):
                        status = "failed"
                    else:
                        status = "in_progress"
            except:
                pass
        projects_data.append({"id": p, "provider": provider, "status": status.capitalize(), "created_at": created_at})
    
    # Sort projects by created date descending
    projects_data.sort(key=lambda x: x["created_at"], reverse=True)
    return render_template("dashboard.html", projects=projects_data)

@app.route("/project/new", methods=["GET", "POST"])
def create_project():
    if request.method == "POST":
        data = request.form
        project_id = data.get("project_name", "untitled_project")
        
        text_control = data.get("text_control", "allow")
        fps = int(data.get("fps", 30))
        transition = data.get("transition", "crossfade")
        subtitles = data.get("subtitles") == "on"
        llm_temperature = float(data.get("llm_temperature", 0.7))
        
        provider = data.get("llm_provider", "local")
        if provider == "cloud":
            llm_config = {"backend": "gemini", "temperature": llm_temperature}
        elif provider == "xai_llm":
            llm_config = {"backend": "xai_llm", "temperature": llm_temperature}
        else:
            llm_config = {"backend": "lmstudio", "model": "local-model", "host": "http://localhost:1234", "temperature": llm_temperature}
            
        img_source = data.get("image_source", "local")
        image_config = {"backend": "auto"}
        if img_source == "cloud":
            image_config["backend"] = "imagerouter"
            image_config["model"] = data.get("image_model", "black-forest-labs/FLUX-2-klein-9b")
            
        bg_source = data.get("bg_source", "local")
        image_config["bg_backend"] = "imagerouter" if bg_source == "cloud" else "local"
        image_config["bg_model"] = data.get("bg_model", "bria/remove-background")
        
        upscale_source = data.get("upscale_source", "local")
        image_config["upscale_backend"] = "imagerouter" if upscale_source == "cloud" else "local"
        image_config["upscale_model"] = data.get("upscale_model", "prunaai/P-Image-Upscale")
        
        # Credit Check
        total_cost_per_scene = 0
        prices_map = {
            "black-forest-labs/FLUX-2-klein-9b": 0.0008,
            "flux/1.1-pro": 0.04,
            "flux/2-klein": 0.00,
            "midjourney": 0.0848,
            "recraft/v4": 0.04,
            "dalle3": 0.04,
            "bria/remove-background": 0.0006,
            "prunaai/P-Image-Upscale": 0.005,
        }
        if img_source == "cloud": total_cost_per_scene += prices_map.get(image_config["model"], 0)
        if bg_source == "cloud": total_cost_per_scene += prices_map.get(image_config["bg_model"], 0)
        if upscale_source == "cloud": total_cost_per_scene += prices_map.get(image_config["upscale_model"], 0)

        if total_cost_per_scene > 0:
            import math
            text = data.get("topic", "").strip()
            word_count = len(text.split())
            est_scenes = max(1, math.ceil(word_count / 15))
            needed_credits = est_scenes * total_cost_per_scene
            
            import requests
            api_key = os.environ.get("IMAGEROUTER_API_KEY", "")
            if not api_key:
                return jsonify({"error": "IMAGEROUTER_API_KEY environment variable is missing."})
            
            try:
                resp = requests.get("https://api.imagerouter.io/v1/credits", headers={"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}, timeout=10)
                if resp.status_code == 200:
                    credits_data = resp.json()
                    rem_credits = float(credits_data.get("remaining_credits", 0))
                    if rem_credits < needed_credits:
                        return jsonify({"error": f"Insufficient API Credits (${needed_credits:.3f} needed). Please refill or switch to Local stages."})
            except Exception as e:
                pass
            
        tts_source = data.get("tts_provider", "local")
        if tts_source == "cloud":
            tts_config = {"backend": "xai", "voice_id": data.get("tts_voice", "eve")}
        else:
            tts_config = {"backend": "kokoro", "voice_id": "af_heart"}
            
        config = {
            "project_name": project_id,
            "topic": data.get("topic"),
            "style": {"mode": "library", "name": data.get("style", "cinematic_dark"), "freetext": ""},
            "llm": llm_config,
            "tts": tts_config,
            "image": image_config,
            "pipeline": {
                "preview_mode": data.get("preview_mode") == "on",
                "aspect_ratio": data.get("aspect_ratio", "16:9"),
                "story_profile": data.get("story_profile", "youtube"),
                "content_type": data.get("content_type", "short"),
                "target_duration": int(data.get("target_duration", 60)),
                "pacing": data.get("pacing", "fast"),
                "motion_source": data.get("motion_source", "local"),
                "2d_effect_style": data.get("2d_effect_style", "mixed"),
                "micro_motion": data.get("micro_motion", "none"),
                "music_genre": data.get("music_genre", ""),
                "music_mode": "local" if data.get("music_file", "").strip() else "generated",
                "music_file": data.get("music_file", "").strip(),
                "text_control": text_control,
                "fps": fps,
                "transition": transition,
                "subtitles": subtitles
            }
        }
        sm = StateManager(project_id)
        
        # Check diffing logic for resumability
        old_config = sm.state.get("config", {})
        if old_config:
            old_pipe = old_config.get("pipeline", {})
            new_pipe = config.get("pipeline", {})
            
            # If fundamental stuff changed, we invalidate story/tts
            if (old_config.get("topic") != config.get("topic") or 
                old_pipe.get("content_type") != new_pipe.get("content_type") or 
                old_pipe.get("target_duration") != new_pipe.get("target_duration") or 
                old_pipe.get("pacing") != new_pipe.get("pacing") or
                old_config.get("llm") != config.get("llm") or
                old_pipe.get("story_profile") != new_pipe.get("story_profile")):
                sm.invalidate_dependents("story")
            
            # If only aspects or styles changed
            elif (old_config.get("style", {}).get("name") != config.get("style", {}).get("name") or 
                  old_pipe.get("text_control") != new_pipe.get("text_control") or 
                  old_config.get("image") != config.get("image")):
                sm.invalidate_dependents("style")
            
            # If TTS changed
            elif old_config.get("tts") != config.get("tts"):
                sm.invalidate_dependents("tts")
                
            # If Motion source changed
            elif old_pipe.get("motion_source") != new_pipe.get("motion_source"):
                sm.invalidate_dependents("parallax")
            
            # If ONLY final wrapper stuff changed
            elif (old_pipe.get("music_genre") != new_pipe.get("music_genre") or 
                  old_pipe.get("music_file") != new_pipe.get("music_file") or 
                  old_pipe.get("fps") != new_pipe.get("fps") or 
                  old_pipe.get("transition") != new_pipe.get("transition") or 
                  old_pipe.get("subtitles") != new_pipe.get("subtitles")):
                sm.invalidate_dependents("music")
                sm.invalidate_dependents("final_video")

        sm.write_config(config)
        
        # Start pipeline thread
        def run_pipe():
            runner = PipelineRunner(project_id, event_callback=lambda event: broadcast(project_id, event))
            runner.run_all()
            
        threading.Thread(target=run_pipe).start()
        return jsonify({"success": True, "redirect": f"/project/{project_id}/progress"})
        
    styles_path = os.path.join("templates", "prompts", "styles.json")
    music_styles_path = os.path.join("templates", "prompts", "music_styles.json")
    styles = []
    music_styles = []
    if os.path.exists(styles_path):
        with open(styles_path, 'r') as f:
            styles = json.load(f)
    if os.path.exists(music_styles_path):
        with open(music_styles_path, 'r') as f:
            music_styles = json.load(f)
    return render_template("create.html", styles=styles, music_styles=music_styles)

@app.route("/settings/styles", methods=["GET", "POST"])
def manage_styles():
    styles_path = os.path.join("templates", "prompts", "styles.json")
    music_styles_path = os.path.join("templates", "prompts", "music_styles.json")
    if request.method == "POST":
        # Overwrite entire json from submitted textarea
        styles_json_str = request.form.get("styles_json", "[]")
        music_styles_json_str = request.form.get("music_styles_json", "[]")
        try:
            styles_data = json.loads(styles_json_str)
            with open(styles_path, "w") as f:
                json.dump(styles_data, f, indent=4)
                
            music_styles_data = json.loads(music_styles_json_str)
            with open(music_styles_path, "w") as f:
                json.dump(music_styles_data, f, indent=4)
                
            return render_template("styles.html", success=True, styles_json=json.dumps(styles_data, indent=4), music_styles_json=json.dumps(music_styles_data, indent=4))
        except Exception as e:
            return render_template("styles.html", error=str(e), styles_json=styles_json_str, music_styles_json=music_styles_json_str)
            
    styles_json_str = "[\n]"
    music_styles_json_str = "[\n]"
    if os.path.exists(styles_path):
        with open(styles_path, 'r') as f:
            styles_json_str = f.read()
    if os.path.exists(music_styles_path):
        with open(music_styles_path, 'r') as f:
            music_styles_json_str = f.read()
    return render_template("styles.html", styles_json=styles_json_str, music_styles_json=music_styles_json_str)

@app.route("/prompts", methods=["GET", "POST"])
def edit_prompts():
    prompt_dir = os.path.join("templates", "prompts")
    if not os.path.exists(prompt_dir): os.makedirs(prompt_dir, exist_ok=True)
    
    if request.method == "POST":
        for file in ["youtube_master.txt", "tiktok_master.txt"]:
            if file in request.form:
                with open(os.path.join(prompt_dir, file), "w") as f:
                    f.write(request.form.get(file))
        return render_template("prompts.html", success=True, 
                               youtube=request.form.get("youtube_master.txt"),
                               tiktok=request.form.get("tiktok_master.txt"))
                               
    yt_code = ""
    yt_path = os.path.join(prompt_dir, "youtube_master.txt")
    if os.path.exists(yt_path):
        with open(yt_path) as f: yt_code = f.read()
        
    tk_code = ""
    tk_path = os.path.join(prompt_dir, "tiktok_master.txt")
    if os.path.exists(tk_path):
        with open(tk_path) as f: tk_code = f.read()

    return render_template("prompts.html", success=False, youtube=yt_code, tiktok=tk_code)

import shutil

@app.route("/project/<project_id>/delete", methods=["POST"])
def delete_project(project_id):
    path = os.path.join("projects", project_id)
    if os.path.exists(path):
        import shutil
        shutil.rmtree(path)
    return jsonify({"success": True, "redirect": "/"})

@app.route("/project/<project_id>/resume", methods=["POST"])
def resume_project(project_id):
    def run_pipe():
        runner = PipelineRunner(project_id, event_callback=lambda event: broadcast(project_id, event))
        runner.run_all()
    threading.Thread(target=run_pipe).start()
    return jsonify({"success": True, "redirect": f"/project/{project_id}/progress"})

@app.route("/project/<project_id>/progress")
def progress(project_id):
    sm = StateManager(project_id)
    return render_template("progress.html", project_id=project_id, state=sm.state)

def broadcast(project_id, event):
    if project_id in log_queues:
        log_queues[project_id].put(event)

@app.route("/project/<project_id>/stream")
def stream(project_id):
    def generate():
        q = log_queues.setdefault(project_id, queue.Queue())
        while True:
            msg = q.get()
            yield f"data: {json.dumps(msg)}\n\n"
            if msg.get("type") == "done":
                break
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7777, debug=True)
