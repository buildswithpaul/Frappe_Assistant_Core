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

"""Which old-system ID became which ERPNext record (#34244).

One row per record an import created from a file that carried the old system's ID. Site-wide, so a
file imported tomorrow, in another session, still finds the records of today's. Written only by the
import engine (utils/import_keys.py); a System Manager can read and delete rows in Desk, nobody
else can open it. The engine checks the user's read access to the target record before it
returns a name.

Used when the consultant doesn't want a field added to the business DocType (the key map is the
fallback of "keep the old ID in a field").
"""

import frappe
from frappe.model.document import Document

UNIQUE_INDEX = "unique_fac_import_key"


class FACImportKeyMap(Document):
    def before_validate(self):
        # the key is compared as text: surrounding spaces are never part of an ID
        self.source_system = (self.source_system or "").strip().lower()
        self.source_key = (self.source_key or "").strip()


def on_doctype_update():
    """One row per (system, DocType, key): the database refuses a second one."""
    frappe.db.add_unique(
        "FAC Import Key Map", ["source_system", "target_doctype", "source_key"], constraint_name=UNIQUE_INDEX
    )
