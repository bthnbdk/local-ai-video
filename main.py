import argparse
import os
import json
import sys
from core.pipeline_runner import PipelineRunner
from core.state_manager import StateManager

def create_project(args):
    project_id = args.project or "default_project"
    print(f"Creating project {project_id}...")
    
    os.makedirs(f"projects/{project_id}", exist_ok=True)
    
    config = {
        "project_name": project_id,
        "topic": args.topic,
        "llm": {"backend": "ollama", "model": "mistral:7b-instruct-q4_K_M", "host": "http://localhost:11434"},
        "tts": {"backend": "kokoro", "voice": "af_sarah", "speed": 1.0},
        "image": {"backend": "auto", "steps": 4, "guidance_scale": 7.5},
        "style": {"mode": "library", "name": args.style, "freetext": ""},
        "pipeline": {"depth_enabled": not args.preview, "music_mode": "none", "preview_mode": args.preview}
    }
    
    sm = StateManager(project_id)
    sm.write_config(config)
    
    print(f"Project '{project_id}' created successfully.")
    
    # Run if requested
    runner = PipelineRunner(project_id)
    runner.run_all()

def run_project(args):
    project_id = args.project
    runner = PipelineRunner(project_id)
    
    if args.stage:
        runner.run_stage(args.stage)
    else:
        runner.run_all()

def delete_project(args):
    project_id = args.project
    path = os.path.join("projects", project_id)
    if os.path.exists(path):
        import shutil
        shutil.rmtree(path)
        print(f"Project '{project_id}' deleted successfully.")
    else:
        print(f"Project '{project_id}' not found.")

def main():
    parser = argparse.ArgumentParser(description="Local AI Video Generator CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    create_parser = subparsers.add_parser("create", help="Create and run a new project")
    create_parser.add_argument("--project", default="video_1", help="Project ID")
    create_parser.add_argument("--topic", required=True, help="Topic for the video")
    create_parser.add_argument("--style", default="cinematic_dark", help="Style name")
    create_parser.add_argument("--preview", action="store_true", help="Enable preview mode (faster, low-res)")
    
    run_parser = subparsers.add_parser("run", help="Run or resume a project")
    run_parser.add_argument("--project", required=True, help="Project ID")
    run_parser.add_argument("--stage", help="Run a specific stage only")
    run_parser.add_argument("--preview", action="store_true", help="Enable preview mode")
    
    status_parser = subparsers.add_parser("status", help="Get project status")
    status_parser.add_argument("--project", required=True, help="Project ID")
    
    delete_parser = subparsers.add_parser("delete", help="Delete a project entirely")
    delete_parser.add_argument("--project", required=True, help="Project ID to delete")
    
    args = parser.parse_args()
    
    if args.command == "create":
        create_project(args)
    elif args.command == "run":
        if args.preview:
            # simple update config
            sm = StateManager(args.project)
            conf = sm.state.get("config", {})
            if "pipeline" not in conf: conf["pipeline"] = {}
            conf["pipeline"]["preview_mode"] = True
            sm.write_config(conf)
            
        run_project(args)
    elif args.command == "status":
        sm = StateManager(args.project)
        print(json.dumps(sm.state["stages"], indent=2))
    elif args.command == "delete":
        delete_project(args)

if __name__ == "__main__":
    main()
