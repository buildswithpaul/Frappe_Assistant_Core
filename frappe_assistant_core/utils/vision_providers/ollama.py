# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Ollama vision provider — local HTTP vision model (e.g., llava, deepseek-ocr)."""

from typing import Any, Dict

import requests

from frappe_assistant_core.utils.vision_providers.base import (
    DEFAULT_OCR_PROMPT,
    VisionProvider,
)


class OllamaProvider(VisionProvider):
    name = "ollama"

    def extract_from_image(self, pil_image) -> Dict[str, Any]:
        url = f"{self.settings['ollama_url']}/api/generate"
        payload = {
            "model": self.settings["ollama_model"],
            "prompt": DEFAULT_OCR_PROMPT,
            "images": [self.encode_jpeg_b64(pil_image)],
            "stream": False,
        }

        response = requests.post(url, json=payload, timeout=self.settings["ollama_timeout"])
        response.raise_for_status()
        data = response.json()

        content = (data.get("response") or "").strip()
        return {
            "success": True,
            "content": content,
            "ocr_backend": self.name,
            "ocr_model": self.settings["ollama_model"],
        }
