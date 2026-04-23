import json
import os
from datetime import datetime

STAGE_DEPENDENCIES = {
    "tts": ["story"],
    "tts_scoring": ["tts"],
    "whisper": ["tts"],
    "scene_timing": ["whisper", "story"],
    "style": [],
    "image_prompts": ["story", "style"],
    "image_gen": ["image_prompts", "style"],
    "image_scoring": ["image_gen"],
    "upscale": ["image_gen"],
    "segmentation": ["image_gen"],
    "depth": ["image_gen"],
    "parallax": ["upscale", "segmentation", "depth", "scene_timing"],
    "overlay": ["parallax", "scene_timing"],
    "audio_post": ["tts"],
    "music": [],
    "final_video": ["overlay", "audio_post", "music"]
}

class StateManager:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.project_dir = os.path.join("projects", project_id)
        self.state_file = os.path.join(self.project_dir, "state.json")
        self.state = self._load_or_create()

    def _load_or_create(self) -> dict:
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        
        state = {
            "project_id": self.project_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "config": {},
            "stages": { stage: {"status": "pending"} for stage in STAGE_DEPENDENCIES.keys() }
        }
        # Add story manually as root
        state["stages"]["story"] = {"status": "pending"}
        for s in ["image_gen", "upscale", "segmentation", "depth", "parallax"]:
            state["stages"][s]["completed_scenes"] = []
            
        self._save(state)
        return state

    def _save(self, state):
        os.makedirs(self.project_dir, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def write_config(self, config: dict):
        self.state["config"] = config
        self._save(self.state)

    def update_stage_status(self, stage: str, status: str, extras: dict = None):
        self.state["stages"][stage]["status"] = status
        self.state["stages"][stage]["updated_at"] = datetime.utcnow().isoformat()
        if extras:
            self.state["stages"][stage].update(extras)
        if status == "completed":
            self.state["updated_at"] = datetime.utcnow().isoformat()
        self._save(self.state)

    def invalidate_dependents(self, changed_stage: str) -> list:
        invalidated = set()
        
        def _recurse_invalidate(stage):
            for s, deps in STAGE_DEPENDENCIES.items():
                if stage in deps:
                    s_data = self.state["stages"].get(s, {})
                    if s_data.get("status") != "pending":
                        s_data["status"] = "pending"
                        s_data["hash"] = None
                        if "completed_scenes" in s_data:
                            s_data["completed_scenes"] = []
                        invalidated.add(s)
                        _recurse_invalidate(s)
        
        _recurse_invalidate(changed_stage)
        self._save(self.state)
        return list(invalidated)
