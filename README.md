# Local AI Video Generation Framework

A production-grade, fully local AI video generation framework optimized for Apple Silicon (MacBook Air M4, 16GB unified RAM).
This system converts a topic or text into a cinematic YouTube video using only local AI tools. 100% LOCAL. NO CLOUD APIS.

## Overview
This tool runs sequentially through 18 stages to produce a full video:
Story Generation -> TTS -> Alignment -> Scene Timing -> Style Engine -> Image Prompts -> Image Generation -> Upscaling -> Depth/Masks -> Parallax -> Overlays -> Audio Post -> Final Render.

## Hardware Requirements
- **Apple Silicon (M1/M2/M3/M4)**. Optimized specifically for M4 with 16GB RAM.
- **Disk Space**: ~20-30GB for models (Ollama, FLUX, Bark/Kokoro, Whisper, MiDaS, RealESRGAN).

| Stage | Model | Approx RAM | Must unload before |
|---|---|---|---|
| Story/Script | Ollama (Mistral 7B Q4) | ~5GB | Image gen |
| TTS | Kokoro (ARM native) | ~1GB | — |
| Alignment | Whisper base | ~1.5GB | Image gen |
| Image gen | FLUX.1-schnell (4-bit) OR SD1.5 | ~7–10GB | LLM |
| Upscale | Real-ESRGAN (tile mode) | ~2GB | — |
| Depth | FastDepth (optional) | ~0.5GB | — |

## Installation
Run the included `setup.sh` script to install system dependencies, setup the python venv, and download required models:
```bash
chmod +x setup.sh
./setup.sh
```

## Model Setup
- **LLM**: Ollama (`mistral:7b-instruct-q4_K_M`)
- **Image**: `mlx-flux` (FLUX.1-schnell in 4-bit) or Diffusers SDXL/SD1.5
- **TTS**: Kokoro ONNX
- **Alignment**: Whisper Timestamped
- **Upscaler**: Real-ESRGAN x4+
- **Depth**: MiDaS v2.1 Small

## Usage - Web UI
Run the Flask server:
```bash
source .venv/bin/activate
python app.py
```
Open `http://localhost:5000`. You can create projects, view progress, and tweak settings.

## Usage - CLI
```bash
# Create and run project
python main.py create --topic "The history of Rome" --style cinematic_dark

# Resume from last completed stage
python main.py run --project myvideo

# Preview mode (faster/smaller)
python main.py run --project myvideo --preview

# See status
python main.py status --project myvideo
```

## JSON Safety System
Features a 4-layer robust parsing architecture:
1. Strict Prompts
2. Pydantic validation
3. Intelligent retries
4. Regex-based auto-fixers for trailing commas & syntax errors

## Memory Management
The Memory Orchestrator actively monitors `psutil` to prevent OOM errors, managing aggressive model unloading and GC sweeps between heavy stages (e.g., LLM -> FLUX).

## License & Notice
All output generated is bound to the licenses of the individual models used (Ollama/Mistral, FLUX, etc.). The framework itself is open source. User is responsible for generated content.
