# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Registry of vision OCR providers.

To add a new provider: implement VisionProvider in a new module, then add it
to PROVIDERS below and to the Select options on Assistant Core Settings.
"""

from typing import Any, Dict

from frappe_assistant_core.utils.vision_providers.base import VisionProvider
from frappe_assistant_core.utils.vision_providers.claude import ClaudeProvider
from frappe_assistant_core.utils.vision_providers.gemini import GeminiProvider
from frappe_assistant_core.utils.vision_providers.ollama import OllamaProvider
from frappe_assistant_core.utils.vision_providers.openai import OpenAIProvider

PROVIDERS = {
    "ollama": OllamaProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}

HOSTED_PROVIDERS = {"claude", "openai", "gemini"}


def get_provider(name: str, settings: Dict[str, Any]) -> VisionProvider:
    if name not in PROVIDERS:
        raise ValueError(f"Unknown vision provider: {name!r}")
    return PROVIDERS[name](settings)


__all__ = [
    "VisionProvider",
    "ClaudeProvider",
    "GeminiProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "PROVIDERS",
    "HOSTED_PROVIDERS",
    "get_provider",
]
