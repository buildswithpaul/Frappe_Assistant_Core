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

"""Session ids for Raven conversations: stable per (place, asker), never shared between askers."""

import uuid

from frappe.utils import get_url

NAMESPACE = uuid.UUID("6f0c2a1e-3b7d-4c55-9a0e-5b1f8d2c4a70")


def session_id_for(place: str, user: str) -> str:
    """One FAC Chat session per Raven place (DM or thread channel) and asker."""
    return str(uuid.uuid5(NAMESPACE, f"raven:{place}:{user}"))


def session_url(session_id: str) -> str:
    return get_url(f"/copilot/chat/{session_id}")
