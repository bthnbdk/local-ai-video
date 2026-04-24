import os
import json
import time
import requests

def get_api_key():
    api_key = os.environ.get("IMAGEROUTER_API_KEY")
    if not api_key:
        raise ValueError("IMAGEROUTER_API_KEY environment variable is missing. Please set it to use Cloud API for images.")
    return api_key

def generate_images_batch(prompts, config, out_dir, log_cb=None):
    api_key = get_api_key()
        
    model = config.get("image", {}).get("model", "black-forest-labs/FLUX-2-klein-9b")
    
    url = "https://api.imagerouter.io/v1/openai/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for p_data in prompts:
        sid = p_data["scene_id"]
        prompt_text = p_data["prompt"]
        out_img = os.path.join(out_dir, f"scene_{sid}.png")
        
        ar = config.get("pipeline", {}).get("aspect_ratio", "16:9")
        if ar == "16:9":
            size_str = "1024x576"
        elif ar == "9:16":
            size_str = "576x1024"
        else:
            size_str = "1024x1024"
            
        if log_cb: log_cb(f"Requesting cloud generation for scene {sid} via {model} ({size_str})...")
        
        payload = {
            "model": model,
            "prompt": prompt_text,
            "size": size_str,
            "response_format": "url",
            "output_format": "png"
        }
        
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code != 200:
                err_body = resp.text
                if "Balance" in err_body or "exhausted" in err_body.lower() or "credits" in err_body.lower():
                    raise RuntimeError("API Credits exhausted. Please refill or switch to Local Generation.")
                raise RuntimeError(f"ImageRouter API Error: {resp.status_code} - {err_body}")
                
            res_data = resp.json()
            img_url = res_data["data"][0]["url"]
            
            # Download the image
            if log_cb: log_cb(f"Downloading image for scene {sid}...")
            # We use requests to get image too
            img_resp = requests.get(img_url, headers={"User-Agent": headers["User-Agent"]}, timeout=60)
            if img_resp.status_code == 200:
                with open(out_img, 'wb') as f:
                    f.write(img_resp.content)
            else:
                raise RuntimeError(f"Failed to download image: {img_resp.status_code} - {img_resp.text}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate cloud image: {str(e)}")
            
        time.sleep(1) # Small delay to respect rate limits
        
    return True

def process_image_edit(img_path, output_path, model_name, log_cb=None):
    api_key = get_api_key()
    url = "https://api.imagerouter.io/v1/openai/images/edits"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    if log_cb:
        log_cb(f"Sending to Cloud API ({model_name})...")
        
    with open(img_path, 'rb') as f:
        files = {
            'image[]': ('image.png', f, 'image/png')
        }
        data = {
            'model': model_name,
            'response_format': 'url'
        }
        
        try:
            resp = requests.post(url, headers=headers, files=files, data=data, timeout=120)
            if resp.status_code != 200:
                err_body = resp.text
                if "Balance" in err_body or "exhausted" in err_body.lower() or "credits" in err_body.lower():
                    raise RuntimeError("API Credits exhausted. Please refill or switch to Local Generation.")
                raise RuntimeError(f"ImageRouter API Edit Error: {resp.status_code} - {err_body}")
                
            res_data = resp.json()
            img_url = res_data["data"][0]["url"]
            
            if log_cb:
                log_cb("Downloading processed image...")
            img_resp = requests.get(img_url, headers={"User-Agent": headers["User-Agent"]}, timeout=60)
            if img_resp.status_code == 200:
                with open(output_path, 'wb') as out_f:
                    out_f.write(img_resp.content)
            else:
                raise RuntimeError(f"Failed to download image: {img_resp.status_code} - {img_resp.text}")
            
        except Exception as e:
             raise RuntimeError(f"Failed image edit with {model_name}: {str(e)}")

def remove_bg_cloud(img_path, output_path, config, log_cb=None):
    model = config.get("image", {}).get("bg_model", "bria/remove-background")
    process_image_edit(img_path, output_path, model, log_cb)
    
def upscale_cloud(img_path, output_path, config, log_cb=None):
    model = config.get("image", {}).get("upscale_model", "prunaai/P-Image-Upscale")
    process_image_edit(img_path, output_path, model, log_cb)
