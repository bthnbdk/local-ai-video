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
    for p in get_projects():
        provider = "Local"
        sm_path = os.path.join("projects", p, "state.json")
        if os.path.exists(sm_path):
            try:
                with open(sm_path) as f:
                    state = json.load(f)
                    if state.get("config", {}).get("llm", {}).get("backend") == "gemini":
                        provider = "Cloud"
            except:
                pass
        projects_data.append({"id": p, "provider": provider})
    return render_template("dashboard.html", projects=projects_data)

@app.route("/project/new", methods=["GET", "POST"])
def create_project():
    if request.method == "POST":
        data = request.form
        project_id = data.get("project_name", "untitled_project")
        
        provider = data.get("llm_provider", "local")
        if provider == "cloud":
            llm_config = {"backend": "gemini"}
        elif provider == "xai_llm":
            llm_config = {"backend": "xai_llm"}
        else:
            llm_config = {"backend": "lmstudio", "model": "local-model", "host": "http://localhost:1234"}
            
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
                "music_genre": data.get("music_genre", ""),
                "music_mode": "local" if data.get("music_file", "").strip() else "generated",
                "music_file": data.get("music_file", "").strip()
            }
        }
        sm = StateManager(project_id)
        sm.write_config(config)
        
        # Start pipeline thread
        def run_pipe():
            runner = PipelineRunner(project_id, event_callback=lambda event: broadcast(project_id, event))
            runner.run_all()
            
        threading.Thread(target=run_pipe).start()
        return jsonify({"success": True, "redirect": f"/project/{project_id}/progress"})
        
    return render_template("create.html")

import shutil

@app.route("/project/<project_id>/delete", methods=["POST"])
def delete_project(project_id):
    path = os.path.join("projects", project_id)
    if os.path.exists(path):
        import shutil
        shutil.rmtree(path)
    return jsonify({"success": True, "redirect": "/"})

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
