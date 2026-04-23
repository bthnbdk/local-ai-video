import os
import json
import urllib.request
import time

def generate_images_batch(prompts, config, out_dir, log_cb=None):
    api_key = os.environ.get("IMAGEROUTER_API_KEY")
    if not api_key:
        raise ValueError("IMAGEROUTER_API_KEY environment variable is missing. Please set it to use Cloud API for images.")
        
    model = config.get("image", {}).get("model", "flux/2-klein")
    
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
