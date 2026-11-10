# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The demo video link: only YouTube, rebuilt from its id, and carried to the Desk in boot info."""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat import demo_video, widget_boot
from frappe_assistant_core.tests.base_test import BaseAssistantTest

VIDEO_ID = "dQw4w9WgXcQ"


class TestDemoVideo(BaseAssistantTest):
    def test_reads_every_youtube_link_shape(self):
        for url in (
            f"https://www.youtube.com/watch?v={VIDEO_ID}",
            f"https://youtube.com/watch?v={VIDEO_ID}&t=3s",
            f"https://m.youtube.com/watch?v={VIDEO_ID}",
            f"https://youtu.be/{VIDEO_ID}?si=abc",
            f"https://www.youtube.com/embed/{VIDEO_ID}",
            f"https://www.youtube.com/shorts/{VIDEO_ID}",
            f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}",
            f"  https://youtu.be/{VIDEO_ID}  ",
        ):
            self.assertEqual(demo_video.youtube_id(url), VIDEO_ID, url)

    def test_refuses_anything_that_is_not_a_youtube_video(self):
        for url in (
            None,
            "",
            42,
            "https://vimeo.com/123456",
            f"https://evil.example/watch?v={VIDEO_ID}",
            f"https://youtube.com.evil.example/watch?v={VIDEO_ID}",
            f"javascript:alert(1)//youtu.be/{VIDEO_ID}",
            "https://www.youtube.com/watch?v=short",
            'https://www.youtube.com/watch?v=dQw4w9WgXc"',
            "https://www.youtube.com/",
            "https://youtu.be/",
        ):
            self.assertIsNone(demo_video.youtube_id(url), url)

    def test_site_config_link_is_rebuilt_from_its_id(self):
        with patch.dict(frappe.conf, {"fac_demo_video_url": f"https://youtu.be/{VIDEO_ID}?si=tracking"}):
            self.assertEqual(
                demo_video.demo_video(),
                {
                    "url": f"https://www.youtube.com/watch?v={VIDEO_ID}",
                    "embed": f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}?rel=0",
                },
            )

    def test_no_link_means_no_video(self):
        with patch.dict(frappe.conf, {"fac_demo_video_url": None}), patch.object(
            demo_video, "DEMO_VIDEO_URL", ""
        ):
            self.assertIsNone(demo_video.demo_video())
        with patch.dict(frappe.conf, {"fac_demo_video_url": "https://vimeo.com/1"}):
            self.assertIsNone(demo_video.demo_video())

    def test_the_built_in_link_is_used_when_the_site_sets_none(self):
        built_in = patch.object(demo_video, "DEMO_VIDEO_URL", f"https://youtu.be/{VIDEO_ID}")
        with patch.dict(frappe.conf, {"fac_demo_video_url": None}), built_in:
            self.assertEqual(demo_video.demo_video()["url"], f"https://www.youtube.com/watch?v={VIDEO_ID}")

    def test_desk_boot_carries_the_video_only_when_set(self):
        bootinfo = frappe._dict()
        with patch.object(demo_video, "demo_video", return_value=None):
            widget_boot.extend_bootinfo(bootinfo, manifest_path="/nonexistent/manifest.json")
        self.assertNotIn("fac_demo_video", bootinfo)

        video = {"url": "u", "embed": "e"}
        with patch.object(demo_video, "demo_video", return_value=video):
            widget_boot.extend_bootinfo(bootinfo, manifest_path="/nonexistent/manifest.json")
        self.assertEqual(bootinfo.fac_demo_video, video)

    def test_a_broken_video_lookup_never_breaks_desk_boot(self):
        bootinfo = frappe._dict()
        with patch.object(demo_video, "demo_video", side_effect=RuntimeError("boom")):
            widget_boot.extend_bootinfo(bootinfo, manifest_path="/nonexistent/manifest.json")
        self.assertNotIn("fac_demo_video", bootinfo)
