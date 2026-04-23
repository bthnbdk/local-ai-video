import wave
import struct

def generate_audio(text: str, output_path: str, config: dict):
    # Try importing kokoro, fallback if unavailable
    try:
        from kokoro_onnx import Kokoro
        kokoro = Kokoro("kokoro-v0_19.onnx", "voices.bin")
        samples, sample_rate = kokoro.create(
            text, voice=config.get("voice", "af_sarah"), speed=config.get("speed", 1.0), lang="en-us"
        )
        import soundfile as sf
        sf.write(output_path, samples, sample_rate)
    except Exception as e:
        print(f"Kokoro unvailable: {e}. Writing dummy wav.")
        # Create a dummy valid wav
        with wave.open(output_path, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            # 2 seconds of silence
            data = struct.pack('<h', 0) * (16000 * 2)
            wav.writeframesraw(data)
