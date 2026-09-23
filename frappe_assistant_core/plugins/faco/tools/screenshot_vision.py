# Frappe Assistant Core - Screenshot vision helper
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

"""Read an uploaded screenshot back as base64 for the vision API.

Shared by every tool that returns a screenshot. The File resolution here is a
security boundary (FACO-M17) — it must exist once, not once per tool.
"""

import base64
import os
from typing import Any, Optional

import frappe


def read_image_content(file_url: str) -> Optional[dict[str, Any]]:
    """Return ``{"format": "jpeg", "data": "<base64>"}`` or None.

    Resolves the File document by URL and uses Frappe's own ``get_full_path``
    rather than trusting the caller-supplied suffix after ``/files/``. A forged
    ``file_url`` (``../../../..``) is rejected at the DB lookup, because no File
    row will match it.

    Never raises: a vision failure must degrade the result, not fail the tool.
    """
    if not file_url:
        return None

    try:
        file_doc = frappe.db.get_value("File", {"file_url": file_url}, ["name", "is_private"], as_dict=True)
        if not file_doc:
            raise frappe.DoesNotExistError(f"Screenshot File record not found for {file_url}")

        file_path = frappe.get_doc("File", file_doc.name).get_full_path()

        # Defence in depth: if anything drifts (custom File subclass, symlink, a
        # future Frappe change), refuse to read rather than trust get_full_path.
        real_path = os.path.realpath(file_path)
        files_root = os.path.realpath(
            frappe.get_site_path("private" if file_doc.is_private else "public", "files")
        )
        if not real_path.startswith(files_root + os.sep):
            raise frappe.PermissionError("Screenshot path escapes files root")

        # Path validated immediately above.
        with open(real_path, "rb") as handle:  # nosemgrep: frappe-security-file-traversal
            image_bytes = handle.read()

        return {"format": "jpeg", "data": base64.b64encode(image_bytes).decode("utf-8")}
    except Exception as e:
        frappe.log_error(title="Screenshot Vision", message=f"Could not read screenshot {file_url}: {e}")
        return None
