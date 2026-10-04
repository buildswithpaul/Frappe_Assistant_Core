# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""``create_web_session`` redirects only to a same-site absolute path (spec §8.3).

Pure: ``_same_site_path`` reads nothing from the site. A browser reads a
backslash as a slash and drops tabs and newlines, so any of those after the
leading ``/`` can turn a path into ``//other.host``.
"""

import unittest

from frappe_assistant_core.chat.api.mobile_stream import DEFAULT_REDIRECT, _same_site_path


class TestSameSitePath(unittest.TestCase):
    def test_a_same_site_absolute_path_survives(self):
        for path in ("/", "/app", "/app/todo?x=1#y", "/app/sales-order/SO-0001", "/app/usuário"):
            with self.subTest(path=path):
                self.assertEqual(_same_site_path(path), path)

    def test_anything_else_falls_back_to_the_desk(self):
        for value in (
            None,
            123,
            ["/app"],
            "",
            "app",
            "//x",
            "https://evil.example",
            "javascript:alert(1)",
            "/\\evil.example",
            "/\t/evil.example",
            "/\n/evil.example",
            "/\x00/evil.example",
            "/\x7f/evil.example",
            "/\x9b/evil.example",
            "/ /evil.example",
            "/　/evil.example",
        ):
            with self.subTest(value=value):
                self.assertEqual(_same_site_path(value), DEFAULT_REDIRECT)
