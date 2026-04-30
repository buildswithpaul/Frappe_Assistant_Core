# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Base class for vision OCR providers (Ollama, Claude, OpenAI, Gemini)."""

import base64
import io
from typing import Any, Dict

DEFAULT_OCR_PROMPT = "Extract all text from this document image exactly as it appears."


class VisionProvider:
    """A vision OCR provider that turns a PIL image into extracted text.

    Subclasses implement extract_from_image(); the registry in
    vision_providers/__init__.py wires them up by name.

    Result shape:
        {"success": bool, "content": str, "ocr_backend": str, "ocr_model": str,
         "usage": {"input_tokens": int, "output_tokens": int, "total_tokens": int,
                   "model": str},
         "error": str (only on failure)}
    """

    name: str = ""

    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings

    def extract_from_image(self, pil_image) -> Dict[str, Any]:
        raise NotImplementedError

    @staticmethod
    def encode_jpeg_b64(pil_image) -> str:
        """JPEG-encode and base64 a PIL image. Matches the prep used by all providers."""
        buf = io.BytesIO()
        if pil_image.mode in ("RGBA", "P"):
            pil_image = pil_image.convert("RGB")
        pil_image.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()

    @staticmethod
    def missing_key_error(provider_label: str, field_label: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": (
                f"{provider_label} API key is not configured. "
                f"Set '{field_label}' in Assistant Core Settings > OCR."
            ),
        }
