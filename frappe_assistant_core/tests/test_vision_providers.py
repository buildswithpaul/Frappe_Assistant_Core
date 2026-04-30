# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Unit tests for hosted vision OCR providers (Claude / OpenAI / Gemini / Ollama).

Tests focus on request shape and response parsing; no real API calls are made.
"""

import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from frappe_assistant_core.utils.vision_providers import (
    HOSTED_PROVIDERS,
    PROVIDERS,
    ClaudeProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
    get_provider,
)


def _tiny_image():
    return Image.new("RGB", (4, 4), color="white")


def _mock_response(json_payload):
    """Build a fake requests.Response."""
    mock = MagicMock()
    mock.json.return_value = json_payload
    mock.raise_for_status.return_value = None
    return mock


class TestRegistry(unittest.TestCase):
    def test_known_providers_resolve(self):
        for name in ["ollama", "claude", "openai", "gemini"]:
            self.assertIn(name, PROVIDERS)
            provider = get_provider(name, {})
            self.assertEqual(provider.name, name)

    def test_unknown_provider_raises(self):
        with self.assertRaises(ValueError):
            get_provider("not-a-provider", {})

    def test_hosted_providers_set(self):
        # Ollama is local — must NOT be in HOSTED_PROVIDERS.
        self.assertEqual(HOSTED_PROVIDERS, {"claude", "openai", "gemini"})


class TestClaudeProvider(unittest.TestCase):
    SETTINGS = {
        "claude_api_key": "sk-ant-test",
        "claude_model": "claude-sonnet-4-6",
        "claude_timeout": 30,
    }

    def test_missing_key_returns_clean_error(self):
        provider = ClaudeProvider({**self.SETTINGS, "claude_api_key": None})
        result = provider.extract_from_image(_tiny_image())
        self.assertFalse(result["success"])
        self.assertIn("Claude API key is not configured", result["error"])

    def test_request_shape_and_response_parsing(self):
        api_response = {
            "content": [{"type": "text", "text": "Invoice #1234\nTotal: $50"}],
            "usage": {"input_tokens": 1500, "output_tokens": 80},
        }
        provider = ClaudeProvider(self.SETTINGS)

        with patch(
            "frappe_assistant_core.utils.vision_providers.claude.requests.post",
            return_value=_mock_response(api_response),
        ) as mock_post:
            result = provider.extract_from_image(_tiny_image())

        # Request shape
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.anthropic.com/v1/messages")
        self.assertEqual(kwargs["headers"]["x-api-key"], "sk-ant-test")
        self.assertEqual(kwargs["headers"]["anthropic-version"], "2023-06-01")
        payload = kwargs["json"]
        self.assertEqual(payload["model"], "claude-sonnet-4-6")
        # First content block should be the image (base64 jpeg)
        image_block = payload["messages"][0]["content"][0]
        self.assertEqual(image_block["type"], "image")
        self.assertEqual(image_block["source"]["media_type"], "image/jpeg")
        self.assertTrue(image_block["source"]["data"])  # non-empty base64

        # Response parsing
        self.assertTrue(result["success"])
        self.assertEqual(result["content"], "Invoice #1234\nTotal: $50")
        self.assertEqual(result["ocr_backend"], "claude")
        self.assertEqual(result["ocr_model"], "claude-sonnet-4-6")
        self.assertEqual(result["usage"]["input_tokens"], 1500)
        self.assertEqual(result["usage"]["output_tokens"], 80)
        self.assertEqual(result["usage"]["total_tokens"], 1580)
        self.assertEqual(result["usage"]["model"], "claude-sonnet-4-6")


class TestOpenAIProvider(unittest.TestCase):
    SETTINGS = {
        "openai_api_key": "sk-test",
        "openai_model": "gpt-4o-mini",
        "openai_base_url": "https://api.openai.com/v1",
        "openai_timeout": 30,
    }

    def test_missing_key_returns_clean_error(self):
        provider = OpenAIProvider({**self.SETTINGS, "openai_api_key": ""})
        result = provider.extract_from_image(_tiny_image())
        self.assertFalse(result["success"])
        self.assertIn("OpenAI API key is not configured", result["error"])

    def test_request_shape_and_response_parsing(self):
        api_response = {
            "choices": [{"message": {"content": "Hello world"}}],
            "usage": {"prompt_tokens": 1100, "completion_tokens": 12, "total_tokens": 1112},
        }
        provider = OpenAIProvider(self.SETTINGS)

        with patch(
            "frappe_assistant_core.utils.vision_providers.openai.requests.post",
            return_value=_mock_response(api_response),
        ) as mock_post:
            result = provider.extract_from_image(_tiny_image())

        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-test")
        payload = kwargs["json"]
        self.assertEqual(payload["model"], "gpt-4o-mini")
        # image_url block must use the data: URI scheme
        image_block = payload["messages"][0]["content"][1]
        self.assertEqual(image_block["type"], "image_url")
        self.assertTrue(image_block["image_url"]["url"].startswith("data:image/jpeg;base64,"))

        self.assertTrue(result["success"])
        self.assertEqual(result["content"], "Hello world")
        self.assertEqual(result["usage"]["input_tokens"], 1100)
        self.assertEqual(result["usage"]["output_tokens"], 12)
        self.assertEqual(result["usage"]["total_tokens"], 1112)

    def test_base_url_override_strips_trailing_slash(self):
        settings = {**self.SETTINGS, "openai_base_url": "https://my-proxy.example.com/v1/"}
        provider = OpenAIProvider(settings)
        api_response = {"choices": [{"message": {"content": ""}}], "usage": {}}

        with patch(
            "frappe_assistant_core.utils.vision_providers.openai.requests.post",
            return_value=_mock_response(api_response),
        ) as mock_post:
            provider.extract_from_image(_tiny_image())

        args, _ = mock_post.call_args
        # Trailing slash on base_url should not produce a double slash.
        self.assertEqual(args[0], "https://my-proxy.example.com/v1/chat/completions")


class TestGeminiProvider(unittest.TestCase):
    SETTINGS = {
        "gemini_api_key": "test-key",
        "gemini_model": "gemini-2.5-flash",
        "gemini_timeout": 30,
    }

    def test_missing_key_returns_clean_error(self):
        provider = GeminiProvider({**self.SETTINGS, "gemini_api_key": None})
        result = provider.extract_from_image(_tiny_image())
        self.assertFalse(result["success"])
        self.assertIn("Gemini API key is not configured", result["error"])

    def test_request_shape_and_response_parsing(self):
        api_response = {
            "candidates": [{"content": {"parts": [{"text": "Receipt total $9.99"}]}}],
            "usageMetadata": {
                "promptTokenCount": 800,
                "candidatesTokenCount": 7,
                "totalTokenCount": 807,
            },
        }
        provider = GeminiProvider(self.SETTINGS)

        with patch(
            "frappe_assistant_core.utils.vision_providers.gemini.requests.post",
            return_value=_mock_response(api_response),
        ) as mock_post:
            result = provider.extract_from_image(_tiny_image())

        args, kwargs = mock_post.call_args
        # API key goes in the URL as a query param
        self.assertIn("gemini-2.5-flash:generateContent", args[0])
        self.assertIn("key=test-key", args[0])
        payload = kwargs["json"]
        # inline_data part must carry mime_type + base64 data
        parts = payload["contents"][0]["parts"]
        self.assertTrue(any("inline_data" in p for p in parts))
        inline = next(p["inline_data"] for p in parts if "inline_data" in p)
        self.assertEqual(inline["mime_type"], "image/jpeg")
        self.assertTrue(inline["data"])

        self.assertTrue(result["success"])
        self.assertEqual(result["content"], "Receipt total $9.99")
        self.assertEqual(result["usage"]["input_tokens"], 800)
        self.assertEqual(result["usage"]["output_tokens"], 7)
        self.assertEqual(result["usage"]["total_tokens"], 807)


class TestOllamaProvider(unittest.TestCase):
    SETTINGS = {
        "ollama_url": "http://localhost:11434",
        "ollama_model": "llava",
        "ollama_timeout": 30,
    }

    def test_request_shape_and_response_parsing(self):
        api_response = {"response": "extracted text"}
        provider = OllamaProvider(self.SETTINGS)

        with patch(
            "frappe_assistant_core.utils.vision_providers.ollama.requests.post",
            return_value=_mock_response(api_response),
        ) as mock_post:
            result = provider.extract_from_image(_tiny_image())

        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://localhost:11434/api/generate")
        payload = kwargs["json"]
        self.assertEqual(payload["model"], "llava")
        self.assertFalse(payload["stream"])
        self.assertEqual(len(payload["images"]), 1)

        self.assertTrue(result["success"])
        self.assertEqual(result["content"], "extracted text")
        self.assertEqual(result["ocr_backend"], "ollama")
        # Ollama doesn't report tokens — usage is absent.
        self.assertNotIn("usage", result)


class TestAuditUsageExtraction(unittest.TestCase):
    """Verifies _extract_usage_fields maps usage dicts to audit log fields."""

    def test_usage_with_all_fields_maps_correctly(self):
        from frappe_assistant_core.utils.audit_trail import _extract_usage_fields

        usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "model": "claude-sonnet-4-6",
        }
        fields = _extract_usage_fields(usage)
        self.assertEqual(fields["input_tokens"], 100)
        self.assertEqual(fields["output_tokens"], 50)
        self.assertEqual(fields["total_tokens"], 150)
        self.assertEqual(fields["llm_model"], "claude-sonnet-4-6")

    def test_missing_total_is_computed(self):
        from frappe_assistant_core.utils.audit_trail import _extract_usage_fields

        fields = _extract_usage_fields({"input_tokens": 10, "output_tokens": 5, "model": "x"})
        self.assertEqual(fields["total_tokens"], 15)

    def test_none_usage_returns_empty(self):
        from frappe_assistant_core.utils.audit_trail import _extract_usage_fields

        self.assertEqual(_extract_usage_fields(None), {})

    def test_empty_usage_returns_empty(self):
        from frappe_assistant_core.utils.audit_trail import _extract_usage_fields

        self.assertEqual(_extract_usage_fields({}), {})

    def test_non_dict_returns_empty(self):
        from frappe_assistant_core.utils.audit_trail import _extract_usage_fields

        self.assertEqual(_extract_usage_fields("not a dict"), {})


if __name__ == "__main__":
    unittest.main()
