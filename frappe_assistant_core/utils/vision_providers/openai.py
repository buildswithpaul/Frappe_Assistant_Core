# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""OpenAI vision provider — Chat Completions API with image_url content blocks.

Configurable base_url so users can point at Azure OpenAI or compatible proxies
(LiteLLM, OpenRouter) without code changes.
"""

from typing import Any, Dict

import requests

from frappe_assistant_core.utils.vision_providers.base import (
    DEFAULT_OCR_PROMPT,
    VisionProvider,
)


class OpenAIProvider(VisionProvider):
    name = "openai"

    def extract_from_image(self, pil_image) -> Dict[str, Any]:
        api_key = self.settings.get("openai_api_key")
        if not api_key:
            return self.missing_key_error("OpenAI", "OpenAI API Key")

        model = self.settings["openai_model"]
        base_url = (self.settings.get("openai_base_url") or "https://api.openai.com/v1").rstrip("/")
        url = f"{base_url}/chat/completions"

        b64 = self.encode_jpeg_b64(pil_image)
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": DEFAULT_OCR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(url, json=payload, headers=headers, timeout=self.settings["openai_timeout"])
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices") or []
        text = ""
        if choices:
            message = choices[0].get("message") or {}
            text = (message.get("content") or "").strip()

        usage = data.get("usage", {}) or {}
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))

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
