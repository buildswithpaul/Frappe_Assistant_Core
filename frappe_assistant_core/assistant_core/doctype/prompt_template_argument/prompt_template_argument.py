# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Prompt Template Argument child table.
Defines arguments/placeholders for prompt templates.
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document


class PromptTemplateArgument(Document):
    def validate(self):
        """Validate argument definition."""
        self.validate_argument_name()
        self.validate_allowed_values()

    def validate_argument_name(self):
        """Ensure argument_name is a valid Python identifier."""
        if not self.argument_name:
            return

        # Must be a valid Python identifier (for Jinja2 compatibility)
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", self.argument_name):
            frappe.throw(
                _("Argument name '{0}' must be a valid identifier "
                  "(start with letter or underscore, contain only letters, numbers, underscores)"
                  ).format(self.argument_name)
            )

    def validate_allowed_values(self):
        """Validate allowed_values for select types."""
        if self.argument_type in ("select", "multiselect"):
            if not self.allowed_values:
                frappe.throw(
                    _("Allowed Values is required for {0} type arguments").format(
                        self.argument_type
                    )
                )
