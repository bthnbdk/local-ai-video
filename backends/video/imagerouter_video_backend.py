import os
import requests
import json
import math

def get_closest_duration(target_duration: float) -> float:
    supported = [1.2, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    for d in supported:
        if d >= target_duration:
            return d
    return 12.0

def generate_video(prompt: str, image_path: str, output_path: str, target_duration: float = 5.0):
    url = "https://api.imagerouter.io/v1/openai/videos/generations"
    headers = {
        "Authorization": f"Bearer {os.environ.get('IMAGEROUTER_API_KEY')}"
    }
    
    seconds = get_closest_duration(target_duration)
    
    prompt = prompt if prompt and len(prompt) > 2 else "cinematic motion, high quality, smooth movement"
    
    # Cap prompt to 3000 chars if somehow longer, though rare
    prompt = prompt[:3000]

    try:
        with open(image_path, "rb") as image_file:
            files = {
                "image": image_file.read()
            }
            payload = {
                "model": "bytedance/seedance-1-pro-fast",
                "prompt": prompt,
                "seconds": seconds
            }

            response = requests.post(url, headers=headers, data=payload, files=files, timeout=600)

        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                video_url = data["data"][0].get("url")
                if video_url:
                    vid_response = requests.get(video_url, timeout=300)
                    if vid_response.status_code == 200:
                        with open(output_path, "wb") as f:
                            f.write(vid_response.content)
                        return True
            raise Exception("Video generation succeeded but URL was missing from the response.")
        else:
            raise Exception(f"API returned status code {response.status_code}: {response.text}")
    except Exception as e:
        raise Exception(f"Failed to generate video: {str(e)}")


