import argparse
import base64
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".heic"}
IE_URL = "https://api.upstage.ai/v1/information-extraction"


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {
            "type": "string",
            "description": "One of notice, assignment, scholarship, receipt, place, or unknown.",
        },
        "title": {
            "type": "string",
            "description": "Main title or representative heading. Empty string if absent.",
        },
        "source": {
            "type": "string",
            "description": "Issuer, store, school office, organization, app, or document source.",
        },
        "created_date": {
            "type": "string",
            "description": "Created, issued, paid, or posted date in YYYY-MM-DD if present.",
        },
        "event_date": {
            "type": "string",
            "description": "Event, visit, meeting, class, or usage date in YYYY-MM-DD if present.",
        },
        "deadline": {
            "type": "string",
            "description": "Application, submission, payment, or reservation deadline in YYYY-MM-DD if present.",
        },
        "deadline_bucket": {
            "type": "string",
            "description": "today, this_week, this_month, future, past, or empty string.",
        },
        "has_submission": {
            "type": "string",
            "description": "true if application/submission/action is requested, false otherwise, unknown if unclear.",
        },
        "amount": {
            "type": "string",
            "description": "Important KRW amount as digits only if present. Empty string if absent.",
        },
        "currency": {
            "type": "string",
            "description": "Currency code such as KRW if money is present. Empty string if absent.",
        },
        "location_name": {
            "type": "string",
            "description": "Venue, store, building, room, or place name if present.",
        },
        "address": {
            "type": "string",
            "description": "Full address if present.",
        },
        "summary": {
            "type": "string",
            "description": "One concise Korean sentence summarizing the important content.",
        },
        "important_texts": {
            "type": "array",
            "description": (
                "Important visible Korean or English text snippets. Include titles, dates, "
                "deadlines, amounts, locations, contacts, requirements, and action items."
            ),
            "items": {"type": "string"},
        },
        "evidence_texts": {
            "type": "array",
            "description": "Short original text snippets supporting the extracted fields.",
            "items": {"type": "string"},
        },
    },
    "required": [
        "doc_type",
        "title",
        "source",
        "created_date",
        "event_date",
        "deadline",
        "deadline_bucket",
        "has_submission",
        "amount",
        "currency",
        "location_name",
        "address",
        "summary",
        "important_texts",
        "evidence_texts",
    ],
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract important text data from images with Upstage Information Extraction."
    )
    parser.add_argument("--images-dir", default="images")
    parser.add_argument("--output", default="outputs/important_texts.json")
    parser.add_argument("--mode", choices=["standard", "enhanced"], default="standard")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=1.1, help="Delay between API calls for 1 RPS limits.")
    parser.add_argument("--force", action="store_true", help="Re-process images already in the output JSON.")
    parser.add_argument("--retry-errors", action="store_true", help="Re-process images with status=error.")
    return parser.parse_args()


def require_api_key():
    load_dotenv()
    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        raise RuntimeError("UPSTAGE_API_KEY is missing. Add it to .env or the environment.")
    return api_key


def list_images(images_dir):
    root = Path(images_dir)
    if not root.exists():
        raise FileNotFoundError(f"Images directory not found: {root}")
    return sorted(path for path in root.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)


def load_existing(output_path):
    if not output_path.exists():
        return {"generated_at": None, "source_dir": None, "count": 0, "results": []}
    with output_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("results", [])
    return data


def save_output(output_path, data):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    data["count"] = len(data.get("results", []))
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def image_to_data_url(image_path):
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:application/octet-stream;base64,{encoded}"


def request_with_retry(method, url, *, max_retries=4, **kwargs):
    wait = 1.0
    for attempt in range(max_retries):
        response = requests.request(method, url, timeout=120, **kwargs)
        if response.status_code not in {429, 500, 502, 503, 504}:
            return response
        if attempt == max_retries - 1:
            return response
        time.sleep(wait)
        wait *= 2
    return response


def extract_with_upstage(api_key, image_path, mode):
    payload = {
        "model": "information-extract",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
                ],
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "important_text_extraction",
                "schema": EXTRACTION_SCHEMA,
            },
        },
        "mode": mode,
        "confidence": True,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = request_with_retry("POST", IE_URL, headers=headers, json=payload)
    if not response.ok:
        raise RuntimeError(f"Upstage IE failed ({response.status_code}): {response.text}")

    raw = response.json()
    message = raw["choices"][0]["message"]
    extracted = json.loads(message["content"])
    return {
        "metadata": normalize_metadata(extracted),
        "summary": clean_string(extracted.get("summary")),
        "important_texts": clean_string_list(extracted.get("important_texts")),
        "evidence_texts": clean_string_list(extracted.get("evidence_texts")),
        "confidence_details": parse_tool_call_arguments(message),
        "usage": raw.get("usage"),
        "model": raw.get("model"),
    }


def parse_tool_call_arguments(message):
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return None
    arguments = tool_calls[0].get("function", {}).get("arguments")
    if not arguments:
        return None
    if isinstance(arguments, dict):
        return arguments
    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        return arguments


def normalize_metadata(extracted):
    amount = normalize_amount(extracted.get("amount"))
    return {
        "doc_type": normalize_choice(
            extracted.get("doc_type"),
            {"notice", "assignment", "scholarship", "receipt", "place", "unknown"},
        ),
        "title": clean_or_none(extracted.get("title")),
        "source": clean_or_none(extracted.get("source")),
        "created_date": normalize_date(extracted.get("created_date")),
        "event_date": normalize_date(extracted.get("event_date")),
        "deadline": normalize_date(extracted.get("deadline")),
        "deadline_bucket": normalize_choice(
            extracted.get("deadline_bucket"),
            {"today", "this_week", "this_month", "future", "past"},
        ),
        "has_submission": normalize_bool(extracted.get("has_submission")),
        "amount": amount,
        "currency": clean_or_none(extracted.get("currency")) or ("KRW" if amount is not None else None),
        "location_name": clean_or_none(extracted.get("location_name")),
        "address": clean_or_none(extracted.get("address")),
    }


def clean_string(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def clean_or_none(value):
    value = clean_string(value)
    return value or None


def clean_string_list(value):
    if not isinstance(value, list):
        return []
    cleaned = []
    seen = set()
    for item in value:
        text = clean_string(item)
        if text and text not in seen:
            cleaned.append(text)
            seen.add(text)
    return cleaned


def normalize_choice(value, allowed):
    value = clean_string(value).lower()
    return value if value in allowed else None


def normalize_bool(value):
    value = clean_string(value).lower()
    if value in {"true", "yes", "y", "1", "있음", "예"}:
        return True
    if value in {"false", "no", "n", "0", "없음", "아니오"}:
        return False
    return None


def normalize_amount(value):
    text = clean_string(value)
    if not text:
        return None
    digits = re.sub(r"[^0-9.]", "", text)
    if not digits:
        return None
    try:
        amount = float(digits)
    except ValueError:
        return None
    return int(amount) if amount.is_integer() else amount


def normalize_date(value):
    text = clean_string(value)
    if not text:
        return None
    match = re.search(r"(20\d{2})[-./년\s]*(\d{1,2})[-./월\s]*(\d{1,2})", text)
    if not match:
        return text
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def main():
    args = parse_args()
    api_key = require_api_key()
    images = list_images(args.images_dir)
    if args.limit is not None:
        images = images[: args.limit]

    output_path = Path(args.output)
    output = load_existing(output_path)
    output["source_dir"] = str(Path(args.images_dir))

    target_ids = {path.stem for path in images}
    existing_by_id = {item.get("image_id"): item for item in output["results"]}
    results = [item for item in output["results"] if item.get("image_id") not in target_ids]

    for index, image_path in enumerate(images, start=1):
        image_id = image_path.stem
        existing = existing_by_id.get(image_id)
        if existing and not args.force and (existing.get("status") == "ok" or not args.retry_errors):
            results.append(existing_by_id[image_id])
            print(f"[skip] {image_path.name}")
            continue

        print(f"[{index}/{len(images)}] extracting {image_path.name}")
        item = {"image_id": image_id, "file_name": image_path.name, "status": "ok"}
        try:
            item.update(extract_with_upstage(api_key, image_path, args.mode))
        except Exception as exc:
            item["status"] = "error"
            item["error"] = str(exc)

        results.append(item)
        output["results"] = sorted(results, key=lambda row: row.get("image_id", ""))
        save_output(output_path, output)
        time.sleep(args.sleep)

    print(f"Saved {len(output['results'])} records to {output_path}")


if __name__ == "__main__":
    main()
