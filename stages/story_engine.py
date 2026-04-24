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
    llm_backend = config.get("llm", {}).get("backend", "local")
    
    story_profile = config.get("pipeline", {}).get("story_profile", "youtube")
    content_type = config.get("pipeline", {}).get("content_type", "short")
    target_duration = config.get("pipeline", {}).get("target_duration", 60)
    pacing = config.get("pipeline", {}).get("pacing", "fast")
    
    target_words = int((target_duration / 60.0) * 140) # ~ 140 words per minute of speech
    pacing_desc = "short, fast-paced scenes" if pacing == "fast" else "longer, descriptive scenes" if pacing == "relaxed" else "documentary rhythm"
    
    prof_path = os.path.join("templates", "prompts", f"{story_profile}_master.txt")
    profile_rules = ""
    if os.path.exists(prof_path):
        with open(prof_path) as f: profile_rules = f.read() + "\n\n"
        
    hook_rule = "You MUST include a strong, engaging hook in the first 3 seconds to immediately capture attention." if content_type == "short" else ""
    
    duration_rules = f"""
TIME & PACING GUIDELINES:
- Target Duration: ~{target_duration} seconds.
- Target Word Count: ~{target_words} words across the entire script.
- Pacing: {pacing_desc}.
{hook_rule}
"""
    
    grok_rules = ""
    if tts_backend == "xai" or llm_backend == "xai_llm":
        grok_rules = """
SPEECH TAG GUIDE (Grok expressive TTS):
You MUST use these tags naturally in the 'text' field to add emotion and timing:
- Inline marks: [pause], [long-pause], [laugh], [chuckle], [sigh], [breath], [cry]
- Wrapping wrappers: <whisper>content</whisper>, <loud>content</loud>, <slow>content</slow>, <fast>content</fast>, <singing>content</singing>, <emphasis>content</emphasis>
Use these tags frequently to make the narration sound expressive and human.

Think step-by-step about the visual flow before outputting the final JSON. Ensure the 'mood' and 'emotion' tags perfectly match the narrative for Grok TTS integration.
"""
    prompt = profile_rules + duration_rules + grok_rules + STRICT_PROMPT.format(
        schema=ScriptJSON.model_json_schema(),
        topic=topic,
        scenes_count=scenes_count
    )
    
    def llm_call(p):
        backend_type = config.get("llm", {}).get("backend", "lmstudio")
        if backend_type == "gemini":
            return gemini_gen(p, config.get("llm", {}))
        elif backend_type == "xai_llm":
            from backends.llm.xai_llm_backend import generate_text as xai_gen
            return xai_gen(p, config.get("llm", {}))
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
