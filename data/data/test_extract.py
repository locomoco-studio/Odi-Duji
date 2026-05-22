import os
import json
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

API_KEY = os.getenv("UPSTAGE_API_KEY")

headers = {
    "Authorization": f"Bearer {API_KEY}"
}

image_path = r"D:\hackathon-devA\dataset\images\img_001.jpg"

url = "https://api.upstage.ai/v1/document-ai/document-parse" 
with open(image_path, "rb") as f:
    files = {
        "document": f
    }

    response = requests.post(
        url,
        headers=headers,
        files=files
    )

result = response.json()

print(json.dumps(result, indent=2, ensure_ascii=False))

Path("outputs/parsed").mkdir(parents=True, exist_ok=True)

with open("outputs/parsed/img_001.json", "w", encoding="utf-8") as out:
    json.dump(result, out, ensure_ascii=False, indent=2)