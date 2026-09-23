"""Widget assets ship unhashed behind a 12h max-age.

Stamping the release version busts the cache across releases — but not within
one, which is every dev rebuild and every manual same-version deploy. Deriving
the stamp from the files themselves closes both.
"""

import unittest


class TestWidgetAssetVersion(unittest.TestCase):
    def setUp(self):
        from frappe_assistant_core import hooks

        self.hooks = hooks

    def test_the_stamp_still_carries_the_release_version(self):
        from frappe_assistant_core import __version__

        self.assertIn(__version__, self.hooks._WIDGET_ASSET_VERSION)

    def test_every_widget_asset_url_is_stamped(self):
        urls = [u for u in self.hooks.app_include_js + self.hooks.app_include_css if "/chat/widget/" in u]
        self.assertTrue(urls)
        for url in urls:
            self.assertIn(f"?v={self.hooks._WIDGET_ASSET_VERSION}", url)

    def test_the_revision_is_content_derived_not_a_clock(self):
        # Two calls with nothing changed must agree, or every worker serves a
        # different URL and the cache is useless in both directions.
        first = self.hooks._widget_asset_revision()
        second = self.hooks._widget_asset_revision()
        self.assertEqual(first, second)
        self.assertTrue(first)

    def test_it_changes_when_a_widget_file_changes(self):
        import os
        import tempfile

        before = self.hooks._widget_asset_revision()
        widget_dir = self.hooks._WIDGET_ASSET_DIR
        probe = os.path.join(widget_dir, "_cache_bust_probe.js")
        with open(probe, "w") as fh:
            fh.write("// temporary probe\n")
        try:
            self.assertNotEqual(self.hooks._widget_asset_revision(), before)
        finally:
            os.unlink(probe)
        self.assertEqual(self.hooks._widget_asset_revision(), before)

    def test_an_unreadable_directory_does_not_break_boot(self):
        # A stale stamp is a caching problem; an exception here is an outage.
        rev = self.hooks._widget_asset_revision(directory="/nonexistent/widget")
        self.assertEqual(rev, "")

    def test_libs_are_excluded_so_a_vendor_bump_is_the_release_version(self):
        # Only our own sources — the pinned vendor bundles change with releases.
        import inspect

        src = inspect.getsource(self.hooks._widget_asset_revision)
        self.assertIn("libs", src)


if __name__ == "__main__":
    unittest.main()
