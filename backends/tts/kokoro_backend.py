import os

def generate_audio(text: str, output_path: str, config: dict):
    from kokoro_onnx import Kokoro
    
    model_path = os.path.join("models", "kokoro", "kokoro-v1.0.onnx")
    voices_path = os.path.join("models", "kokoro", "voices-v1.0.bin")
    
    if not os.path.exists(model_path) or not os.path.exists(voices_path):
        raise FileNotFoundError(f"Missing Kokoro models! Expected inside: {model_path} and {voices_path}. Please execute setup.sh to download v1.0 dependencies.")
        
    kokoro = Kokoro(model_path, voices_path)
    samples, sample_rate = kokoro.create(
        text, voice=config.get("voice", "af_sarah"), speed=config.get("speed", 1.0), lang="en-us"
    )
    
    import soundfile as sf
    sf.write(output_path, samples, sample_rate)
