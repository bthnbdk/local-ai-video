import gc
from PIL import Image

flux_model_instance = None

def init_model(log_cb=None):
    global flux_model_instance
    try:
        from mflux import Flux1, Config
        if log_cb: log_cb("Loading Flux1 (mflux) with strict 4-bit quantization...")
        flux_model_instance = Flux1(name="flux1-schnell", quantize=4, local_path=None)
    except ImportError:
        if log_cb: log_cb("mflux not installed. Fallback dummy mode active.")
        flux_model_instance = None

def generate_image(prompt: str, negative_prompt: str, seed: int, output_path: str, preview: bool):
    global flux_model_instance
    try:
        if flux_model_instance is not None:
            # mflux Flux1.generate_image signature
            img_result = flux_model_instance.generate_image(
                seed=seed,
                prompt=prompt,
                steps=4
            )
            # mflux typically returns an object with a .image PIL attribute or acts as one
            if hasattr(img_result, 'image'):
                image = img_result.image
            else:
                image = img_result # fallback if it returns directly
                
            if preview:
                image = image.resize((512, 288))
            image.save(output_path)
        else:
            raise ImportError("Model not loaded because mflux is unavailable")
            
    except Exception as e:
        print(f"mflux generation failed ({e}). Fallback to dummy solid color.")
        img = Image.new('RGB', (512 if preview else 1024, 288 if preview else 576), color = (73, 109, 137))
        img.save(output_path)

def cleanup():
    global flux_model_instance
    if flux_model_instance is not None:
        del flux_model_instance
        flux_model_instance = None
    
    gc.collect()
    try:
        import mlx.core as mx
        mx.metal.clear_cache()
    except ImportError:
        pass
