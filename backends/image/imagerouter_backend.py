import os
import json
import urllib.request
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
        "Content-Type": "application/json"
    }

    for p_data in prompts:
        sid = p_data["scene_id"]
        prompt_text = p_data["prompt"]
        out_img = os.path.join(out_dir, f"scene_{sid}.png")
        
        if log_cb: log_cb(f"Requesting cloud generation for scene {sid} via {model}...")
        
        payload = {
            "model": model,
            "prompt": prompt_text,
            "n": 1,
            "size": "1024x1024",
            "response_format": "url"
        }
        
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=120) as r:
                res_data = json.loads(r.read().decode())
                
            img_url = res_data["data"][0]["url"]
            
            # Download the image
            if log_cb: log_cb(f"Downloading image for scene {sid}...")
            urllib.request.urlretrieve(img_url, out_img)
            
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            if "Balance" in err_body or "exhausted" in err_body.lower() or "credits" in err_body.lower():
                raise RuntimeError("API Credits exhausted. Please refill or switch to Local Generation.")
            raise RuntimeError(f"ImageRouter API Error: {e.code} - {err_body}")
        except Exception as e:
            raise RuntimeError(f"Failed to generate cloud image: {str(e)}")
            
        time.sleep(1) # Small delay to respect rate limits
        
    return True

def process_image_edit(img_path, output_path, model_name, log_cb=None):
    api_key = get_api_key()
    url = "https://api.imagerouter.io/v1/openai/images/edits"
    
    if log_cb:
        log_cb(f"Sending to Cloud API ({model_name})...")
        
    with open(img_path, 'rb') as f:
        files = {
            'image': ('image.png', f, 'image/png')
        }
        data = {
            'model': model_name,
            'response_format': 'url'
        }
        
        try:
            resp = requests.post(url, headers={"Authorization": f"Bearer {api_key}"}, files=files, data=data, timeout=120)
            if resp.status_code != 200:
                err_body = resp.text
                if "Balance" in err_body or "exhausted" in err_body.lower() or "credits" in err_body.lower():
                    raise RuntimeError("API Credits exhausted. Please refill or switch to Local Generation.")
                raise RuntimeError(f"ImageRouter API Edit Error: {resp.status_code} - {err_body}")
                
            res_data = resp.json()
            img_url = res_data["data"][0]["url"]
            
            if log_cb:
                log_cb("Downloading processed image...")
            urllib.request.urlretrieve(img_url, output_path)
            
        except Exception as e:
             raise RuntimeError(f"Failed image edit with {model_name}: {str(e)}")

def remove_bg_cloud(img_path, output_path, config, log_cb=None):
    model = config.get("image", {}).get("bg_model", "bria/remove-background")
    process_image_edit(img_path, output_path, model, log_cb)
    
def upscale_cloud(img_path, output_path, config, log_cb=None):
    model = config.get("image", {}).get("upscale_model", "prunaai/P-Image-Upscale")
    process_image_edit(img_path, output_path, model, log_cb)
