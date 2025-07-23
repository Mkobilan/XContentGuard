import os
import requests
from PIL import Image
from imagehash import dhash
import io
from collections import Counter
import numpy as np
from math import sqrt

def cosine_similarity(vec1, vec2):
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])
    sum1 = sum([vec1[x]**2 for x in vec1.keys()])
    sum2 = sum([vec2[x]**2 for x in vec2.keys()])
    denominator = sqrt(sum1) * sqrt(sum2)
    if not denominator:
        return 0.0
    return float(numerator) / denominator

def detect_theft(original_text, candidate_text, original_hash=None, candidate_img_url=None):
    # Local text similarity (cosine with bag-of-words)
    original_words = Counter(original_text.lower().split())
    candidate_words = Counter(candidate_text.lower().split())
    text_score = cosine_similarity(original_words, candidate_words)

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