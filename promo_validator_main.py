"""
Promotional Image Validator — standalone FastAPI server.

Exposes a single POST endpoint:
  POST /validate_promo

Accepts the same product JSON format as the main image checker:
{
  "category": "...",
  "title":    "...",
  "description": "...",
  "images": [
    {"id": 123, "position_id": 2, "image": "https://..."}
  ]
}

Returns per-image promotional analysis results.

Usage:
  python promo_validator_main.py [--host 0.0.0.0] [--port 8001]
"""

from __future__ import annotations

import argparse
import sys
import os
import traceback
from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI, HTTPException

# Ensure project root is on sys.path so services/ and utils/ resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.validator import validate_image

app = FastAPI(
    title="Promotional Text Validator",
    version="1.0.0",
    description="4-stage AI pipeline for marketplace promotional text detection",
)


# ---------------------------------------------------------------------------
# REQUEST PROCESSING
# ---------------------------------------------------------------------------

def _process_request(data: Dict[str, Any]) -> List[Dict]:
    category    = data.get("category", "unknown")
    title       = data.get("title", "")
    description = data.get("description", "")
    images      = data.get("images", [])

    if not images:
        raise ValueError("No images provided in request")

    results = []
    for img_data in images:
        image_url  = img_data.get("image", "")
        image_id   = img_data.get("id", 0)
        position_id = img_data.get("position_id")

        if not image_url:
            results.append({
                "image_id":   image_id,
                "error":      "No image URL provided",
                "is_promotional": False,
                "confidence_score": 0,
            })
            continue

        # Per-image title/description override (optional)
        img_title = img_data.get("title", title)
        img_desc  = img_data.get("description", description)
        img_cat   = img_data.get("category", category)

        try:
            result = validate_image(
                image_url=image_url,
                title=img_title,
                description=img_desc,
                category=img_cat,
                image_id=image_id,
                use_semantic=True,
            )
            if position_id is not None:
                result["position_id"] = position_id
            results.append(result)

        except Exception as exc:
            results.append({
                "image_id":         image_id,
                "position_id":      position_id,
                "error":            str(exc),
                "is_promotional":   False,
                "confidence_score": 0,
                "reason":           "Processing error — image could not be analysed",
                "_traceback":       traceback.format_exc(),
            })

    return results


# ---------------------------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------------------------

@app.post("/validate_promo")
@app.post("/validate_promo/")
async def validate_promo(data: Dict[str, Any]):
    """Main promotional text validation endpoint."""
    try:
        results = _process_request(data)
        # Return array for multiple images, plain dict for single
        return results if len(results) != 1 else results[0]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/validate_promo/health")
async def health():
    return {"status": "healthy", "service": "Promotional Text Validator", "version": "1.0.0"}


@app.get("/validate_promo/info")
async def info():
    return {
        "pipeline_stages": [
            "Stage 0a: CV layout analysis (banner strips, coloured regions)",
            "Stage 0b: Body-native text classification (per OCR box)",
            "Stage 1:  OCR text extraction (EasyOCR)",
            "Stage 2:  Semantic context matching (vocab + fuzzy + sentence-transformer)",
            "Stage 3:  Promotional pattern engine (13 regex categories)",
        ],
        "decision_thresholds": {
            "is_promotional":  "confidence >= 60",
            "flag_for_review": "confidence 35–59",
        },
    }


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Promotional Text Validator Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    print("=" * 60)
    print("Promotional Text Validator")
    print("=" * 60)
    print(f"Starting on {args.host}:{args.port}")
    print(f"Docs: http://{args.host}:{args.port}/docs")
    print("=" * 60)

    uvicorn.run("promo_validator_main:app", host=args.host, port=args.port,
                reload=False, workers=1)


if __name__ == "__main__":
    main()
