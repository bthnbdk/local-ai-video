import json
import os
import urllib.request
import re

VALID_INLINE_TAGS = ['[pause]', '[long-pause]', '[laugh]', '[chuckle]', '[sigh]', '[breath]', '[cry]']
VALID_WRAPPER_TAGS = ['<whisper>', '</whisper>', '<loud>', '</loud>', '<slow>', '</slow>', '<fast>', '</fast>', '<singing>', '</singing>', '<emphasis>', '</emphasis>']

def cleanup_text(text: str) -> str:
    # A simple regex cleanup to remove unsupported tags, but primarily relying on the prompt to generate valid ones.
    def replace_bracket(match):
        tag = match.group(0)
        return tag if tag in VALID_INLINE_TAGS else ""

    def replace_angle(match):
        tag = match.group(0)
        # handle closing tags
        is_closing = tag.startswith("</")
        base_tag = tag if not is_closing else f"<{tag[2:]}"
        
        # Check if base_tag is in VALID_WRAPPER_TAGS
        if base_tag in VALID_WRAPPER_TAGS or tag in VALID_WRAPPER_TAGS:
            return tag
        return ""

    text = re.sub(r'\[.*?\]', replace_bracket, text)
    text = re.sub(r'<.*?>', replace_angle, text)
    return text.strip()

def generate_speech(text: str, config: dict, out_file: str) -> bool:
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise ValueError("XAI_API_KEY environment variable is missing. Please set it to use Grok TTS.")

    voice_id = config.get("voice_id", "eve")

    url = "https://api.x.ai/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    clean_text = cleanup_text(text)

    payload = {
        "model": "tts-1",
        "input": clean_text,
        "voice": voice_id,
        "language": "en",
        "output_format": {"codec": "wav", "sample_rate": 44100}
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            with open(out_file, 'wb') as f:
                f.write(r.read())
        return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise RuntimeError(f"x.ai TTS API Error: {e.code} - {err_body}")
    except Exception as e:
        raise RuntimeError(f"Failed to generate x.ai speech: {str(e)}")
