import os
import requests
from PIL import Image
from imagehash import dhash
import io

def detect_theft(original_text, candidate_text, original_hash=None, candidate_img_url=None):
    # Text similarity via Grok API
    api_key = os.getenv('GROK_API_KEY')
    if not api_key:
        return 0.0  # Placeholder if no key
    url = 'https://api.x.ai/v1/chat/completions'  # Grok API endpoint; confirm at https://x.ai/api
    payload = {
        "model": "grok-beta",
        "messages": [{"role": "user", "content": f"Compute semantic similarity between text1: '{original_text}' and text2: '{candidate_text}'. Return only a float score 0-1."}]
    }
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        score_text = response.json()['choices'][0]['message']['content'].strip()
        try:
            text_score = float(score_text)
        except ValueError:
            text_score = 0.0
    else:
        text_score = 0.0

    # Image hash comparison
    image_score = 0.0
    if original_hash and candidate_img_url:
        img_response = requests.get(candidate_img_url)
        if img_response.status_code == 200:
            img = Image.open(io.BytesIO(img_response.content))
            candidate_hash = dhash(img)
            difference = original_hash - candidate_hash  # Hamming distance
            image_score = 1.0 if difference < 10 else 0.0  # Threshold for match

    # Average scores
    return (text_score + image_score) / 2 if original_hash else text_score