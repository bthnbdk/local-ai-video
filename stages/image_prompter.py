import os
import json
from core.schemas import ImagePromptJSON
from core.json_parser import parse_llm_json
from backends.llm.ollama_backend import generate_text

def run(project_dir: str, config: dict, log_cb=None):
    script_file = os.path.join(project_dir, "script.json")
    style_file = os.path.join(project_dir, "style.json")
    
    if not os.path.exists(script_file) or not os.path.exists(style_file):
        raise FileNotFoundError("Missing script.json or style.json")
        
    prompts_dir = os.path.join(project_dir, "prompts")
    os.makedirs(prompts_dir, exist_ok=True)
    
    with open(script_file) as f: script = json.load(f)
    with open(style_file) as f: style = json.load(f)
    
    if log_cb: log_cb("Generating image prompts...")
    
    for scene in script.get("scenes", []):
        sid = scene["id"]
        
        # In a real run, we'd use LLM to enhance. For local constraints, we compose it directly or do simple LLM
        prompt = f"{scene['visual_hint']}, {scene['emotion']} emotion, {scene['shot_type']} shot, {style['base_prompt']}, {style['color_palette']}, {style['lighting']}, {style['camera']}, {style['texture']}"
        neg_prompt = style["negative_prompt"]
        
        out_obj = {
            "scene_id": sid,
            "prompt": prompt,
            "negative_prompt": neg_prompt
        }
        
        with open(os.path.join(prompts_dir, f"scene_{sid}.json"), "w") as f:
            json.dump(out_obj, f, indent=2)
            
    if log_cb: log_cb(f"Generated {len(script.get('scenes', []))} prompts.")
    return True
