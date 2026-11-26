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

"""One MCP task: a tools/call the client polls with tasks/get (spec §7.4).

Written and read only by ``mcp/tasks.py``, which checks ``owner_user`` on every access. No
result is stored: each poll rebuilds it from the reference document, so report rows and import
content are never copied into a table a System Manager can read for every user.
"""

from frappe.model.document import Document


class FACMCPTask(Document):
    pass
