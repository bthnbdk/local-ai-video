from flask import Flask, render_template, request, Response, stream_with_context, jsonify
import queue
import json
import os
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
    return render_template("dashboard.html", projects=get_projects())

@app.route("/project/new", methods=["GET", "POST"])
def create_project():
    if request.method == "POST":
        data = request.form
        project_id = data.get("project_name", "untitled_project")
        
        config = {
            "project_name": project_id,
            "topic": data.get("topic"),
            "style": {"mode": "library", "name": data.get("style", "cinematic_dark"), "freetext": ""},
            "llm": {"backend": "ollama", "model": "mistral"},
            "tts": {"backend": "kokoro"},
            "image": {"backend": "auto"},
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
    app.run(host="0.0.0.0", port=3000, debug=True)
