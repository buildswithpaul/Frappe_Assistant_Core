# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""A full page stored in the database and shown by the ``fac-pages`` Desk page."""

import re

import frappe
from frappe import _
from frappe.model.document import Document

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SLUG_MAX_LENGTH = 80


class FACPage(Document):
    def validate(self):
        self.validate_slug()

    def validate_slug(self):
        if len(self.slug or "") > SLUG_MAX_LENGTH or not SLUG_PATTERN.match(self.slug or ""):
            frappe.throw(
                _(
                    "Slug must be lower-case letters and digits in words joined by single hyphens, "
                    "at most {0} characters."
                ).format(SLUG_MAX_LENGTH)
            )
