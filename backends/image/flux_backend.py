from PIL import Image

def generate_image(prompt: str, negative_prompt: str, seed: int, output_path: str, preview: bool):
    try:
        from mlx_flux.pipeline import FluxPipeline
        pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell")
        image = pipe(prompt, num_inference_steps=4, seed=seed).images[0]
        if preview:
            image = image.resize((512, 288))
        image.save(output_path)
    except Exception as e:
        print(f"MLX-Flux unavailable ({e}). Fallback to dummy solid color.")
        img = Image.new('RGB', (512 if preview else 1024, 288 if preview else 576), color = (73, 109, 137))
        img.save(output_path)
