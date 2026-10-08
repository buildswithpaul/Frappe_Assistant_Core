# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The Desk loads the widget only through the built manifest's entry."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat import widget_boot

BASE = "/assets/frappe_assistant_core/chat/widget-app/"


def _manifest(dirpath, records):
    os.makedirs(os.path.join(dirpath, ".vite"), exist_ok=True)
    path = os.path.join(dirpath, ".vite", "manifest.json")
    with open(path, "w") as fh:
        json.dump(records, fh)
    return path


class TestWidgetBoot(unittest.TestCase):
    def setUp(self):
        widget_boot._cache.clear()

    def test_reads_the_entry_and_the_stylesheet_record(self):
        # Shape of a real build with cssCodeSplit:false: the stylesheet is its own record.
        with tempfile.TemporaryDirectory() as d:
            path = _manifest(
                d,
                {
                    "src/widget/main.js": {"file": "assets/main.abc.js", "isEntry": True},
                    "_chunk.js": {"file": "assets/chunk.def.js"},
                    "style.css": {"file": "assets/style.123.css", "src": "style.css"},
                },
            )
            self.assertEqual(
                widget_boot.widget_entry(path),
                {"entry": BASE + "assets/main.abc.js", "css": [BASE + "assets/style.123.css"]},
            )

    def test_collects_css_arrays_and_dedupes(self):
        with tempfile.TemporaryDirectory() as d:
            path = _manifest(
                d,
                {
                    "src/widget/main.js": {"file": "assets/main.abc.js", "css": ["assets/a.css"]},
                    "src/widget/panel.js": {
                        "file": "assets/panel.def.js",
                        "css": ["assets/a.css", "assets/b.css"],
                    },
                    "style.css": {"file": "assets/b.css"},
                },
            )
            self.assertEqual(
                widget_boot.widget_entry(path)["css"],
                [BASE + "assets/a.css", BASE + "assets/b.css"],
            )

    def test_no_manifest_means_no_widget_and_no_error(self):
        self.assertIsNone(widget_boot.widget_entry("/nonexistent/manifest.json"))

    def test_a_corrupt_manifest_means_no_widget(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".vite"))
            path = os.path.join(d, ".vite", "manifest.json")
            with open(path, "w") as fh:
                fh.write("{not json")
            self.assertIsNone(widget_boot.widget_entry(path))

    def test_boot_info_carries_it_only_when_built(self):
        bootinfo = frappe._dict()
        widget_boot.extend_bootinfo(bootinfo, manifest_path="/nonexistent/manifest.json")
        self.assertNotIn("fac_widget", bootinfo)

    def test_boot_info_carries_the_entry_when_built(self):
        with tempfile.TemporaryDirectory() as d:
            path = _manifest(d, {"src/widget/main.js": {"file": "assets/main.abc.js"}})
            bootinfo = frappe._dict()
            widget_boot.extend_bootinfo(bootinfo, manifest_path=path)
            self.assertEqual(bootinfo.fac_widget, {"entry": BASE + "assets/main.abc.js", "css": []})

    def test_a_non_string_entry_file_means_no_widget(self):
        for bad in (None, "", 7, ["a.js"]):
            widget_boot._cache.clear()
            with tempfile.TemporaryDirectory() as d:
                path = _manifest(d, {"src/widget/main.js": {"file": bad}})
                self.assertIsNone(widget_boot.widget_entry(path), repr(bad))

    def test_malformed_css_values_are_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            path = _manifest(
                d,
                {
                    "src/widget/main.js": {
                        "file": "assets/main.abc.js",
                        "css": [{"x": 1}, "assets/ok.css", 3],
                    },
                    "other.js": {"file": "assets/o.js", "css": "ab.css"},
                    "style.css": {"file": 5},
                },
            )
            self.assertEqual(widget_boot.widget_entry(path)["css"], [BASE + "assets/ok.css"])

    def test_extend_bootinfo_never_raises(self):
        bootinfo = frappe._dict()
        with patch.object(widget_boot, "widget_entry", side_effect=RuntimeError("boom")):
            widget_boot.extend_bootinfo(bootinfo)
        self.assertNotIn("fac_widget", bootinfo)

    def test_the_hook_is_registered(self):
        from frappe_assistant_core import hooks

        self.assertIn("frappe_assistant_core.chat.widget_boot.extend_bootinfo", hooks.extend_bootinfo)

    def test_the_desk_loads_only_the_bootstrap_and_diagnostics(self):
        from frappe_assistant_core import hooks

        widget_js = [u.split("?")[0] for u in hooks.app_include_js if "/chat/widget/" in u]
        self.assertEqual(
            widget_js,
            [
                "/assets/frappe_assistant_core/chat/widget/widget_diagnostics_redact.js",
                "/assets/frappe_assistant_core/chat/widget/widget_diagnostics_recorder.js",
                "/assets/frappe_assistant_core/chat/widget/widget_loader.js",
            ],
        )
        self.assertFalse([u for u in hooks.app_include_css if "/chat/widget/" in u])
