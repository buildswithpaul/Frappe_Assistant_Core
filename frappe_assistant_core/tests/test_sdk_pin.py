# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""FAC must never call an SDK symbol absent from the version FAC pins.

This is a pure file/attribute read — no database, no Frappe context — so it is
plain unittest, not FrappeTestCase.

What it does catch: a forgotten pin bump, a `>=` floor sneaking back in, and a
connect method FAC's proxy calls that the installed SDK does not define.

What it CANNOT catch: whether 1.9.0 is actually on PyPI. In local dev the SDK
is installed editable (`pip install -e apps/assistant_runtime_sdk`), so this
test reads the source tree, not the published artifact. Only a clean-venv
install of the pinned version proves publication.
"""

import re
import unittest
from pathlib import Path

import assistant_runtime_sdk
import tomllib

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

CONNECT_METHODS = (
    "begin_mcp_connect",
    "get_mcp_connect_session",
    "commit_mcp_connect",
    "abandon_mcp_connect",
    "begin_mcp_reauth",
)


class TestSDKPin(unittest.TestCase):
    def _requirement(self) -> str:
        with open(PYPROJECT, "rb") as fh:
            data = tomllib.load(fh)
        for dep in data["project"]["dependencies"]:
            if dep.replace(" ", "").startswith("assistant_runtime_sdk"):
                return dep.replace(" ", "")
        self.fail("frappe_assistant_core does not depend on assistant_runtime_sdk at all")

    def test_the_pin_is_exact_never_a_floor(self):
        requirement = self._requirement()
        self.assertRegex(
            requirement,
            r"^assistant_runtime_sdk==\d+\.\d+\.\d+",
            f"pin must be ==X.Y.Z, got {requirement!r}. A >= floor lets pip resolve an "
            "older published version missing the methods FAC calls.",
        )

    def test_the_pinned_version_is_the_one_installed(self):
        pinned = re.sub(r"^assistant_runtime_sdk==", "", self._requirement())
        self.assertEqual(pinned, assistant_runtime_sdk.__version__)

    def test_the_installed_sdk_defines_every_connect_method_fac_calls(self):
        # FAC's own tests mock the SDK with MagicMock, which answers any
        # attribute. This is the only assertion in FAC that touches the real class.
        from assistant_runtime_sdk.client import AssistantRuntimeClient

        for name in CONNECT_METHODS:
            self.assertTrue(hasattr(AssistantRuntimeClient, name), name)


if __name__ == "__main__":
    unittest.main()
