import json
import re
from pydantic import BaseModel, ValidationError
from typing import Type, TypeVar, Callable

T = TypeVar("T", bound=BaseModel)

def clean_json_string(raw: str) -> str:
    """Strip markdown fences, leading/trailing whitespace, BOM."""
    raw = str(raw).strip().lstrip('\ufeff')
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
    return raw.strip()

def auto_fix_json(raw: str) -> str:
    """Attempt common JSON syntax repairs."""
    # Remove trailing commas before } or ]
    raw = re.sub(r',\s*([\}\]])', r'\1', raw)
    # Replace single quotes with double quotes (naively, for simple cases)
    # Only if no double quotes present at all
    if '"' not in raw and "'" in raw:
        raw = raw.replace("'", '"')
    # Truncate to last valid closing brace/bracket
    for end_char in ('}', ']'):
        idx = raw.rfind(end_char)
        if idx != -1:
            candidate = raw[:idx+1]
            try:
                json.loads(candidate)
                return candidate
            except Exception:
                pass
    return raw

def parse_llm_json(
    raw: str,
    schema: Type[T],
    llm_call: Callable[[str], str],
    retry_prompt_template: str,
    max_retries: int = 3
) -> T:
    last_error = None
    current_raw = raw

    for attempt in range(max_retries):
        try:
            cleaned = clean_json_string(current_raw)
            if not cleaned:
                raise ValueError("Empty response from LLM")
            parsed = json.loads(cleaned)
            return schema.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            # Layer 4: auto-fix attempt
            try:
                fixed = auto_fix_json(clean_json_string(current_raw))
                parsed = json.loads(fixed)
                return schema.model_validate(parsed)
            except Exception:
                pass
            
            # Retry with fix prompt
            if attempt < max_retries - 1:
                fix_prompt = retry_prompt_template.format(
                    error=str(e),
                    previous_output=current_raw
                )
                print(f"[JSON Parser] Attempt {attempt+1} failed. Retrying...")
                current_raw = llm_call(fix_prompt)

    raise ValueError(f"JSON parsing failed after {max_retries} attempts: {last_error}")
