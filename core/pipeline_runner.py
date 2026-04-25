import os
import json
import traceback
from core.state_manager import StateManager
from core.memory_orchestrator import orchestrator
from stages import (
    story_engine, tts_engine, tts_scorer, whisper_aligner, scene_timing,
    style_engine, image_prompter, image_generator, image_scorer,
    upscaler, segmenter, depth_estimator, parallax_engine,
    overlay_engine, audio_post, music_system, final_video
)

STAGE_MAP = {
    "story": story_engine.run,
    "tts": tts_engine.run,
    "tts_scoring": tts_scorer.run,
    "whisper": whisper_aligner.run,
    "scene_timing": scene_timing.run,
    "style": style_engine.run,
    "image_prompts": image_prompter.run,
    "image_gen": image_generator.run,
    "image_scoring": image_scorer.run,
    "upscale": upscaler.run,
    "segmentation": segmenter.run,
    "depth": depth_estimator.run,
    "parallax": parallax_engine.run,
    "overlay": overlay_engine.run,
    "audio_post": audio_post.run,
    "music": music_system.run,
    "final_video": final_video.run
}

class PipelineRunner:
    def __init__(self, project_id: str, event_callback=None):
        self.project_id = project_id
        self.project_dir = os.path.join("projects", project_id)
        self.state_manager = StateManager(project_id)
        self.event_callback = event_callback or (lambda x: None)
        
    def log(self, message: str, level="info"):
        out = f"[{self.project_id}] {message}"
        print(out)
        log_path = os.path.join(self.project_dir, "project_log.txt")
        try:
            with open(log_path, "a") as f:
                f.write(out + "\n")
        except: pass
        self.event_callback({"type": "log", "level": level, "message": message})

    def check_stage_outputs(self, stage_name: str) -> bool:
        if stage_name == "story":
            return os.path.exists(os.path.join(self.project_dir, "script.json"))
        elif stage_name == "tts":
            return os.path.exists(os.path.join(self.project_dir, "audio.wav"))
        elif stage_name == "whisper":
            return os.path.exists(os.path.join(self.project_dir, "alignment.json"))
        elif stage_name in ["image_gen", "segmentation", "upscale", "parallax"]:
            script_path = os.path.join(self.project_dir, "script.json")
            if not os.path.exists(script_path): return False
            try:
                with open(script_path) as f:
                    script = json.load(f)
                scenes_count = len(script.get("scenes", []))
                
                target_dir = ""
                if stage_name == "image_gen": target_dir = "images"
                elif stage_name == "segmentation": target_dir = "masks"
                elif stage_name == "upscale": target_dir = "upscaled"
                elif stage_name == "parallax": target_dir = "parallax"
                
                out_dir = os.path.join(self.project_dir, target_dir)
                if not os.path.exists(out_dir): return False
                
                files = [f for f in os.listdir(out_dir) if f.endswith(".png") or f.endswith(".mp4")]
                return len(files) >= scenes_count and scenes_count > 0
            except:
                return False
        return False

    def run_stage(self, stage_name: str) -> bool:
        if stage_name not in STAGE_MAP:
            self.log(f"Stage {stage_name} skipped (not implemented).", "warn")
            return True
            
        stage_state = self.state_manager.state["stages"].get(stage_name, {})
        if stage_state.get("status") == "completed" or self.check_stage_outputs(stage_name):
            self.log(f"Stage {stage_name} outputs found. Skipping to save time/costs.")
            self.state_manager.update_stage_status(stage_name, "completed", {"hash": "TBD"})
            return True

        self.state_manager.update_stage_status(stage_name, "running")
        self.log(f"Starting stage: {stage_name}")
        
        try:
            # Memory check before starting heavy stages happens inside the runner/models
            config = self.state_manager.state.get("config", {})
            func = STAGE_MAP[stage_name]
            result = func(self.project_dir, config, self.log)
            
            self.state_manager.update_stage_status(stage_name, "completed", {"hash": "TBD"})
            self.log(f"Stage {stage_name} completed successfully.")
            
            # Invalidate downstream
            inv = self.state_manager.invalidate_dependents(stage_name)
            if inv:
                self.log(f"Invalidated downstream stages: {inv}")
                
            return True
            
        except Exception as e:
            err_msg = str(e)
            self.log(f"Stage {stage_name} failed: {err_msg}", "error")
            traceback.print_exc()
            self.state_manager.update_stage_status(stage_name, "failed", {"error": err_msg})
            return False

    def run_all(self):
        config = self.state_manager.state.get("config", {})
        self.log("=== PROJECT CONFIGURATION ===")
        self.log(json.dumps(config, indent=2))
        
        stages = [
            "story", "tts", "tts_scoring", "whisper", "scene_timing", "style", "image_prompts",
            "image_gen", "image_scoring", "upscale", "segmentation", "depth", "parallax",
            "overlay", "audio_post", "music", "final_video"
        ]
        
        for stage in stages:
            if not self.run_stage(stage):
                self.log("Pipeline stopped due to stage failure.", "error")
                break
                
        self.event_callback({"type": "done", "status": "completed"})
