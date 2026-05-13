# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Regression tests for Jinja sandbox on Prompt Template rendering.

A plain `jinja2.Environment` is not sandboxed: a template like
`{{ ''.__class__.__mro__[1].__subclasses__() }}` exposes the full Python class
graph and is a textbook SSTI payload. `preview_template` is whitelisted to any
logged-in user, and stored templates can be authored by Assistant users — so
all three Jinja construction sites must use `SandboxedEnvironment`, which
raises `SecurityError` on unsafe attribute lookups.

These tests pin the construction sites by inspecting their resolved env type
and by attempting a representative SSTI payload at each entry point.
"""

import unittest

from jinja2.exceptions import SecurityError
from jinja2.sandbox import SandboxedEnvironment

from frappe_assistant_core.api.handlers.prompts import PromptTemplateManager

# A canonical SSTI probe: reach `object` via `__class__.__mro__[1]`, then list
# `__subclasses__()`. In an unsandboxed env this returns a long list of classes;
# in a sandboxed env it raises SecurityError on the `__class__` lookup.
SSTI_PAYLOAD = "{{ ''.__class__.__mro__[1].__subclasses__() }}"


class TestPromptTemplateSandbox(unittest.TestCase):
    def test_manager_jinja_env_is_sandboxed(self):
        """PromptTemplateManager._jinja_env must be a SandboxedEnvironment."""
        manager = PromptTemplateManager()
        self.assertIsInstance(manager._jinja_env, SandboxedEnvironment)

    def test_manager_render_blocks_ssti(self):
        """A SSTI payload through the manager render path raises SecurityError."""
        manager = PromptTemplateManager()
        tmpl = manager._jinja_env.from_string(SSTI_PAYLOAD)
        with self.assertRaises(SecurityError):
            tmpl.render()

    def test_preview_template_blocks_ssti(self):
        """The whitelisted preview_template endpoint must not return Python
        internals when fed a SSTI payload. SandboxedEnvironment raises
        SecurityError on the `__class__` lookup; the function's broad
        try/except converts that to an `Error: ...` string, which is the
        observable signal that the sandbox engaged."""
        from frappe_assistant_core.assistant_core.doctype.prompt_template import prompt_template

        result = prompt_template.preview_template(
            template_content=SSTI_PAYLOAD,
            rendering_engine="Jinja2",
            arguments={},
        )

        # The exact wording isn't load-bearing; what matters is (a) we did not
        # leak a Python subclass list, and (b) the failure surfaces as the
        # SecurityError path, not silent success.
        self.assertIsInstance(result, str)
        self.assertTrue(
            result.startswith("Error:"),
            f"Expected sandbox-blocked error response, got: {result!r}",
        )
        self.assertNotIn("<class '", result)


if __name__ == "__main__":
    unittest.main()
