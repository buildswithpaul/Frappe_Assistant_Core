# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Anthropic Claude vision provider — Messages API with image content blocks."""

from typing import Any, Dict

import requests

from frappe_assistant_core.utils.vision_providers.base import (
    DEFAULT_OCR_PROMPT,
    VisionProvider,
)

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_API_VERSION = "2023-06-01"


class ClaudeProvider(VisionProvider):
    name = "claude"

    def extract_from_image(self, pil_image) -> Dict[str, Any]:
        api_key = self.settings.get("claude_api_key")
        if not api_key:
            return self.missing_key_error("Claude", "Claude API Key")

        model = self.settings["claude_model"]
        payload = {
            "model": model,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": self.encode_jpeg_b64(pil_image),
                            },
                        },
                        {"type": "text", "text": DEFAULT_OCR_PROMPT},
                    ],
                }
            ],
        }
        headers = {
            "x-api-key": api_key,
            "anthropic-version": CLAUDE_API_VERSION,
            "content-type": "application/json",
        }

        response = requests.post(
            CLAUDE_API_URL,
            json=payload,
            headers=headers,
            timeout=self.settings["claude_timeout"],
        )
        response.raise_for_status()
        data = response.json()

        # Concatenate all text blocks (usually one) from the response.
        content_blocks = data.get("content", [])
        text = "".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        ).strip()

        usage = data.get("usage", {}) or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)

        return {
            "success": True,
            "content": text,
            "ocr_backend": self.name,
            "ocr_model": model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "model": model,
            },
        }
