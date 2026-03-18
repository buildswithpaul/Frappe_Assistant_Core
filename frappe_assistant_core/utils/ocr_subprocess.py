# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Standalone PaddleOCR subprocess worker.

Runs in an isolated process to protect the Frappe worker from PaddleOCR
hangs and out-of-memory crashes. No Frappe imports — communicates via
JSON over stdin/stdout.

Usage:
    python -m frappe_assistant_core.utils.ocr_subprocess < request.json
"""

import json
import sys


def _configure_paddle_env():
    """Set environment variables to suppress PaddlePaddle startup noise.

    Must be called before importing paddleocr/paddlepaddle.
    """
    import os

    # Skip model source connectivity check (can hang on air-gapped servers)
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    # Suppress PaddlePaddle verbose logs
    os.environ.setdefault("GLOG_minloglevel", "2")


def _page_to_text(page_result):
    """Convert a single page of PaddleOCR results to structured text.

    PaddleOCR 3.x returns OCRResult dict-like objects with parallel arrays:
      - rec_texts: list of recognized text strings
      - rec_scores: list of confidence scores
      - dt_polys: list of bounding box polygons (4-point, [[x1,y1],[x2,y2],[x3,y3],[x4,y4]])

    Groups text regions into lines based on vertical position,
    then sorts left-to-right within each line. This preserves
    table column alignment.
    """
    if not page_result:
        return ""

    # Handle PaddleOCR 3.x OCRResult (dict-like with parallel arrays)
    if hasattr(page_result, "__getitem__") and not isinstance(page_result, list):
        texts = page_result.get("rec_texts", []) if hasattr(page_result, "get") else page_result["rec_texts"]
        polys = page_result.get("dt_polys", []) if hasattr(page_result, "get") else page_result["dt_polys"]

        if not texts:
            return ""

        # Extract (y_center, x_left, text) from parallel arrays
        positioned_texts = []
        for i, text in enumerate(texts):
            if i < len(polys):
                bbox = polys[i]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                y_center = (float(bbox[0][1]) + float(bbox[3][1])) / 2
                x_left = float(bbox[0][0])
            else:
                # No bbox available; append at end
                y_center = float("inf")
                x_left = 0.0
            positioned_texts.append((y_center, x_left, text))

    # Handle legacy PaddleOCR 2.x format: list of [bbox, (text, score)]
    elif isinstance(page_result, list):
        positioned_texts = []
        for region in page_result:
            bbox = region[0]
            text = region[1][0] if isinstance(region[1], (list, tuple)) else str(region[1])
            y_center = (bbox[0][1] + bbox[3][1]) / 2
            x_left = bbox[0][0]
            positioned_texts.append((y_center, x_left, text))
    else:
        return str(page_result)

    if not positioned_texts:
        return ""

    # Sort by vertical position
    positioned_texts.sort(key=lambda t: t[0])

    # Group into lines: regions within 10px vertical distance
    # are considered part of the same line
    lines = []
    current_line = [positioned_texts[0]]

    for item in positioned_texts[1:]:
        if abs(item[0] - current_line[0][0]) < 10:
            current_line.append(item)
        else:
            lines.append(current_line)
            current_line = [item]
    lines.append(current_line)

    # Sort each line left-to-right, join with tabs for table structure
    text_lines = []
    for line in lines:
        line.sort(key=lambda t: t[1])
        text_lines.append("\t".join(item[2] for item in line))

    return "\n".join(text_lines)


def _result_to_text(result):
    """Convert single-image PaddleOCR result to text.

    For a single image, result is a list with one OCRResult element.
    """
    if not result:
        return ""
    return _page_to_text(result[0])


def _ocr_image(file_path, language):
    """OCR a single image file."""
    import numpy as np
    from paddleocr import PaddleOCR
    from PIL import Image

    ocr = PaddleOCR(lang=language)
    image = Image.open(file_path)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    result = ocr.predict(np.array(image))
    text = _result_to_text(result)

    if not text.strip():
        return {"success": True, "content": "", "message": "No text detected in image"}

    return {"success": True, "content": text}


def _ocr_pdf(file_path, language, max_pages):
    """OCR a PDF file using PaddleOCR's native PDF support."""
    from paddleocr import PaddleOCR

    ocr = PaddleOCR(lang=language)
    result = ocr.predict(file_path)

    if not result:
        return {
            "success": True,
            "content": "",
            "message": "OCR completed but no text was detected in the PDF pages.",
            "pages": 0,
        }

    num_pages = min(len(result), max_pages)
    text_parts = []

    for i in range(num_pages):
        page_text = _page_to_text(result[i])
        if page_text.strip():
            text_parts.append(f"--- Page {i + 1} ---\n{page_text}")

    combined = "\n\n".join(text_parts)

    if not combined.strip():
        return {
            "success": True,
            "content": "",
            "message": "OCR completed but no text was detected in the PDF pages.",
            "pages": num_pages,
        }

    return {
        "success": True,
        "content": combined,
        "pages": num_pages,
        "ocr_pages_with_text": len(text_parts),
    }


def warm_models():
    """Pre-download PaddleOCR models without running inference.

    Initializing PaddleOCR triggers model download from HuggingFace/AIStudio/BOS
    if models are not already cached at ~/.paddlex/official_models/.
    """
    try:
        request = json.loads(sys.stdin.read())
        _configure_paddle_env()

        language = request.get("language", "en")

        from paddleocr import PaddleOCR

        # Initialization triggers model download; no inference needed
        PaddleOCR(lang=language)

        json.dump({"success": True, "message": f"PaddleOCR models for '{language}' are ready."}, sys.stdout)

    except Exception as e:
        error_result = {"success": False, "error": str(e)}
        json.dump(error_result, sys.stdout)
        print(str(e), file=sys.stderr)
        sys.exit(1)


def run_ocr():
    """Main entry point. Reads JSON request from stdin, writes JSON response to stdout."""
    try:
        request = json.loads(sys.stdin.read())

        # Configure PaddlePaddle environment before any imports
        _configure_paddle_env()

        file_path = request["file_path"]
        file_type = request.get("file_type", "image")
        language = request.get("language", "en")
        max_pages = request.get("max_pages", 50)

        if file_type == "pdf":
            result = _ocr_pdf(file_path, language, max_pages)
        else:
            result = _ocr_image(file_path, language)

        json.dump(result, sys.stdout)

    except Exception as e:
        error_result = {"success": False, "error": str(e)}
        json.dump(error_result, sys.stdout)
        print(str(e), file=sys.stderr)
        sys.exit(1)


def main():
    """Dispatch based on action field in the JSON request.

    Supports:
      {"action": "warm", "language": "en"}  — pre-download models
      {"action": "ocr", ...} or no action   — run OCR (default)
    """
    # Peek at stdin to determine action without consuming it
    raw_input = sys.stdin.read()

    try:
        request = json.loads(raw_input)
    except (json.JSONDecodeError, ValueError):
        print("Invalid JSON input", file=sys.stderr)
        sys.exit(1)

    action = request.get("action", "ocr")

    # Re-feed the parsed input back via stdin replacement
    sys.stdin = __import__("io").StringIO(raw_input)

    if action == "warm":
        warm_models()
    else:
        run_ocr()


if __name__ == "__main__":
    main()
