# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Google Gemini vision provider — generateContent endpoint with inline_data parts."""

from typing import Any, Dict

import requests

from frappe_assistant_core.utils.vision_providers.base import (
    DEFAULT_OCR_PROMPT,
    VisionProvider,
)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(VisionProvider):
    name = "gemini"

    def extract_from_image(self, pil_image) -> Dict[str, Any]:
        api_key = self.settings.get("gemini_api_key")
        if not api_key:
            return self.missing_key_error("Gemini", "Gemini API Key")

        model = self.settings["gemini_model"]
        url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": DEFAULT_OCR_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": self.encode_jpeg_b64(pil_image),
                            }
                        },
                    ]
                }
            ]
        }

        response = requests.post(url, json=payload, timeout=self.settings["gemini_timeout"])
        response.raise_for_status()
        data = response.json()

        text = ""
        candidates = data.get("candidates") or []
        if candidates:
            parts = ((candidates[0].get("content") or {}).get("parts")) or []
            text = "".join(p.get("text", "") for p in parts).strip()

        usage = data.get("usageMetadata", {}) or {}
        input_tokens = int(usage.get("promptTokenCount") or 0)
        output_tokens = int(usage.get("candidatesTokenCount") or 0)
        total_tokens = int(usage.get("totalTokenCount") or (input_tokens + output_tokens))

        return {
            "success": True,
            "content": text,
            "ocr_backend": self.name,
            "ocr_model": model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "model": model,
            },
        }
