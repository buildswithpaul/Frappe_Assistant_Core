# Frappe Assistant Core - FAC Chat service worker renderer tests
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for serving FAC Chat's service worker at /copilot/sw.js."""

import os
import tempfile
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat import service_worker
from frappe_assistant_core.chat.service_worker import FACChatServiceWorker
from frappe_assistant_core.tests.base_test import BaseAssistantTest


@contextmanager
def renderer_for(path: str, chat_enabled: bool = True):
    # The /copilot/<path> route rule hands renderers the rewritten path "copilot";
    # only frappe.local.request still carries the URL the browser asked for.
    previous = getattr(frappe.local, "request", None)
    frappe.local.request = SimpleNamespace(path=path)
    try:
        # Chat is off on a fresh install; production turns it on through the
        # toggle_chat admin action, which is what this flag stands in for.
        with patch.object(service_worker, "is_chat_enabled", return_value=chat_enabled):
            yield FACChatServiceWorker("copilot")
    finally:
        frappe.local.request = previous


class TestServiceWorkerRouting(BaseAssistantTest):
    def can_render(self, path: str, chat_enabled: bool = True) -> bool:
        with renderer_for(path, chat_enabled) as renderer:
            return renderer.can_render()

    def test_serves_the_worker_path(self):
        self.assertTrue(self.can_render("/copilot/sw.js"))

    def test_leaves_other_spa_paths_to_the_page(self):
        self.assertFalse(self.can_render("/copilot/chat"))
        self.assertFalse(self.can_render("/copilot/sw.js.map"))

    def test_declines_when_chat_is_off(self):
        # The request then reaches the /copilot page, which answers 404.
        self.assertFalse(self.can_render("/copilot/sw.js", chat_enabled=False))


class TestServiceWorkerResponse(BaseAssistantTest):
    def render_with_build(self, content: bytes | None):
        with tempfile.TemporaryDirectory() as app_dir:
            if content is not None:
                spa = os.path.join(app_dir, "public", "chat", "spa")
                os.makedirs(spa)
                with open(os.path.join(spa, "sw.js"), "wb") as f:
                    f.write(content)
            with patch.object(frappe, "get_app_path", lambda app, *parts: os.path.join(app_dir, *parts)):
                return FACChatServiceWorker("copilot").render()

    def test_serves_the_built_worker_uncached(self):
        response = self.render_with_build(b"self.skipWaiting();")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(), b"self.skipWaiting();")
        self.assertEqual(response.mimetype, "text/javascript")
        # Revalidated on each update check, so a deploy reaches installed apps.
        self.assertIn("no-cache", response.headers["Cache-Control"])

    def test_404_before_the_frontend_is_built(self):
        self.assertEqual(self.render_with_build(None).status_code, 404)
