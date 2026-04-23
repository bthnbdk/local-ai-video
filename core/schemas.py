from pydantic import BaseModel, field_validator
from typing import Literal, List, Optional

class Scene(BaseModel):
    id: int
    text: str
    visual_hint: str
    emotion: str
    shot_type: str

class ScriptJSON(BaseModel):
    title: str
    style: str
    scenes: List[Scene]

class ImagePromptJSON(BaseModel):
    scene_id: int
    prompt: str
    negative_prompt: str

class TimingScene(BaseModel):
    scene_id: int
    start: float
    end: float

class TimingJSON(BaseModel):
    scenes: List[TimingScene]

class StyleJSON(BaseModel):
    style_name: str
    base_prompt: str
    color_palette: str
    lighting: str
    camera: str
    texture: str
    negative_prompt: str
