#!/bin/bash
set -e

echo "=== Local AI Video Generator Setup (macOS + Apple Silicon) ==="

# 1. Homebrew dependencies
brew install ffmpeg python@3.11 git-lfs

# 2. Python virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Python packages
pip install --upgrade pip
pip install -r requirements.txt

# 4. Ollama
if ! command -v ollama &> /dev/null; then
    brew install ollama
fi
ollama serve &
sleep 3
ollama pull mistral:7b-instruct-q4_K_M

# 5. Model: Real-ESRGAN
mkdir -p models/realesrgan
curl -L -o models/realesrgan/RealESRGAN_x4plus.pth \
  "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"

# 6. Model: MiDaS small (depth, optional)
mkdir -p models/midas
curl -L -o models/midas/midas_v21_small_256.pt \
  "https://github.com/isl-org/MiDaS/releases/download/v2_1/midas_v21_small_256.pt"

# 7. Kokoro TTS (ARM native ONNX)
pip install kokoro-onnx
mkdir -p models/kokoro
curl -L -o models/kokoro/kokoro-v1.0.onnx \
  "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v1.0.onnx"
curl -L -o models/kokoro/voices-v1.0.bin \
  "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices-v1.0.bin"

# 8. mflux (FLUX on Apple Silicon via MLX)
pip install mflux

# 9. Whisper Timestamped
pip install whisper-timestamped

# 10. Utilities
pip install rembg basicsr realesrgan timm diffusers transformers accelerate google-generativeai python-dotenv google-auth websockets

# 11. Audiocraft (No-deps to prevent Torch downgrade on Apple Silicon)
pip install --no-deps audiocraft==1.3.0

echo ""
echo "=== Setup complete ==="
echo "Run: source .venv/bin/activate"
echo "Web UI: python app.py"
echo "CLI: python main.py create --topic 'Your topic' --style cinematic_dark"
