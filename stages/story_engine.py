import os
import json
from core.json_parser import parse_llm_json
from core.schemas import ScriptJSON
from backends.llm.gemini_backend import generate_text as gemini_gen
from backends.llm.lmstudio_backend import generate_text as lmstudio_gen, eject_model as lmstudio_eject
from backends.llm.ollama_backend import generate_text as ollama_gen

STRICT_PROMPT = """You MUST return valid JSON only.

STRICT RULES:
- Output ONLY the JSON object/array. Nothing else.
- Do NOT include explanations, comments, or markdown
- Do NOT include trailing commas
- Use double quotes for ALL keys and string values
- Ensure syntactically valid JSON per RFC 8259

Follow this exact schema:
{schema}

Topic: {topic}
Create a high-quality script with {scenes_count} scenes.
Return JSON now:"""

RETRY_PROMPT = """Your previous output was invalid JSON.
Error: {error}

Rules:
- Do NOT change content — only fix syntax
- Remove any markdown code fences
- Ensure all keys and strings use double quotes
- Remove trailing commas
- Return ONLY the corrected JSON

Previous output:
{previous_output}

Corrected JSON:"""

def run(project_dir: str, config: dict, log_cb=None):
    topic = config.get("topic", "Default topic")
    scenes_count = max(3, min(12, len(topic.split()) // 5))
    if scenes_count < 3: scenes_count = 3
    
    tts_backend = config.get("tts", {}).get("backend", "local")
    
    grok_rules = ""
    if tts_backend == "xai":
        grok_rules = """
SPEECH TAG GUIDE (Grok expressive TTS):
You MUST use these tags naturally in the 'text' field to add emotion and timing:
- Inline marks: [pause], [long-pause], [laugh], [chuckle], [sigh], [breath], [cry]
- Wrapping wrappers: <whisper>content</whisper>, <loud>content</loud>, <slow>content</slow>, <fast>content</fast>, <singing>content</singing>, <emphasis>content</emphasis>
Use these tags frequently to make the narration sound expressive and human.
"""
    prompt = grok_rules + STRICT_PROMPT.format(
        schema=ScriptJSON.model_json_schema(),
        topic=topic,
        scenes_count=scenes_count
    )
    
    def llm_call(p):
        backend_type = config.get("llm", {}).get("backend", "lmstudio")
        if backend_type == "gemini":
            return gemini_gen(p, config.get("llm", {}))
        elif backend_type == "ollama":
            return ollama_gen(p, config.get("llm", {}))
        return lmstudio_gen(p, config.get("llm", {}))
        
    if log_cb: log_cb("Generating story from LLM...")
    raw_response = llm_call(prompt)
    
    # parse + fix layers
    script_obj = parse_llm_json(raw_response, ScriptJSON, llm_call, RETRY_PROMPT)
    
    out_path = os.path.join(project_dir, "script.json")
    with open(out_path, "w") as f:
        f.write(script_obj.model_dump_json(indent=2))
        
    if config.get("llm", {}).get("backend", "lmstudio") == "lmstudio":
        try:
            if log_cb: log_cb("Ejecting LM Studio model to free RAM...")
            lmstudio_eject(config.get("llm", {}))
        except Exception as e:
            if log_cb: log_cb(f"Warning: Failed to eject model: {e}")
        
    if log_cb: log_cb(f"Story engine finished. Output saved to {out_path}.")
    return True
