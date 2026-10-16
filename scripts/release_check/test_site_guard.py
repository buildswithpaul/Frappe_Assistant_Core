"""Plain unittest (no Frappe): the guard that keeps the setup scripts off real sites.

Exception to BaseAssistantTest is deliberate: this tests dev tooling and needs no site.
"""

import json
import tempfile
import unittest
from pathlib import Path

import site_guard


class TestSiteGuard(unittest.TestCase):
    def _site(self, config) -> str:
        sites = tempfile.TemporaryDirectory()
        self.addCleanup(sites.cleanup)
        site_dir = Path(sites.name) / "rc.test"
        site_dir.mkdir()
        if config is not None:
            (site_dir / "site_config.json").write_text(
                config if isinstance(config, str) else json.dumps(config)
            )
        return sites.name

    def test_marked_site_is_allowed(self):
        site_guard.require_release_check_site(self._site({"release_check_site": 1}), "rc.test")

    def test_unmarked_site_is_refused_with_the_command_to_mark_it(self):
        with self.assertRaises(SystemExit) as refused:
            site_guard.require_release_check_site(self._site({"db_name": "x"}), "rc.test")

        self.assertIn("set-config release_check_site 1", str(refused.exception))

    def test_marker_set_to_zero_is_refused(self):
        with self.assertRaises(SystemExit):
            site_guard.require_release_check_site(self._site({"release_check_site": 0}), "rc.test")

    def test_missing_or_unreadable_config_is_refused(self):
        for label, config in (("missing", None), ("not json", "{oops"), ("not an object", "[1]")):
            with self.subTest(label), self.assertRaises(SystemExit):
                site_guard.require_release_check_site(self._site(config), "rc.test")


if __name__ == "__main__":
    unittest.main()
