from typing import List, Optional

class StageContract:
    """Base definition for stage required inputs and outputs."""
    required_inputs: List[str]
    outputs: List[str]
    fallback: Optional[str] = None

class StoryEngineContract(StageContract):
    required_inputs = []  # Takes topic from config
    outputs = ["script.json"]

class TTSEngineContract(StageContract):
    required_inputs = ["script.json"]
    outputs = ["audio.wav"]

class TTSScoringContract(StageContract):
    required_inputs = ["audio.wav"]
    outputs = ["scored_audio.json"]

class WhisperContract(StageContract):
    required_inputs = ["audio.wav"]
    outputs = ["alignment.json"]

class SceneTimingContract(StageContract):
    required_inputs = ["script.json", "alignment.json"]
    outputs = ["timing.json"]

class StyleEngineContract(StageContract):
    required_inputs = [] # Takes config/library
    outputs = ["style.json"]

class ImagePromptsContract(StageContract):
    required_inputs = ["script.json", "style.json"]
    outputs = ["prompts/scene_{id}.json"] # conceptual

class ImageGenContract(StageContract):
    required_inputs = ["prompts/scene_{id}.json", "style.json"]
    outputs = ["images/scene_{id}.png"]
    
class ImageScoringContract(StageContract):
    required_inputs = ["images/scene_{id}.png", "prompts/scene_{id}.json"]
    outputs = ["scored_images.json"]

class UpscaleContract(StageContract):
    required_inputs = ["images/scene_{id}.png"]
    outputs = ["upscaled/scene_{id}.png"]

class SegmentationContract(StageContract):
    required_inputs = ["upscaled/scene_{id}.png"]
    outputs = ["masks/scene_{id}.png"]

class DepthContract(StageContract):
    required_inputs = ["upscaled/scene_{id}.png"]
    outputs = ["depth/scene_{id}.png"]

class ParallaxContract(StageContract):
    required_inputs = ["upscaled/scene_{id}.png", "masks/scene_{id}.png", "timing.json"]
    outputs = ["scenes/scene_{id}.mp4"]

class OverlayContract(StageContract):
    required_inputs = ["scenes/scene_{id}.mp4", "timing.json", "script.json"]
    outputs = ["overlaid/scene_{id}.mp4"]

class AudioPostContract(StageContract):
    required_inputs = ["audio.wav"]
    outputs = ["audio_final.wav"]

class MusicContract(StageContract):
    required_inputs = ["timing.json", "script.json", "audio.wav"]
    outputs = ["music.wav"]

class FinalVideoContract(StageContract):
    required_inputs = ["overlaid/scene_{id}.mp4", "audio_final.wav", "music.wav"]
    outputs = ["final/output.mp4"]
