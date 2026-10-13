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

"""Session ids for Raven conversations: stable per (place, asker), never shared between askers.

The id is keyed by the site's encryption key. A session with no saved messages passes FAC Chat's
owner check, so an id anyone could compute would let them claim another person's conversation.
"""

import hashlib
import hmac
import uuid

from frappe.utils import get_url
from frappe.utils.password import get_encryption_key


def _secret() -> str:
    return get_encryption_key()


def session_id_for(place: str, user: str) -> str:
    """One FAC Chat session per Raven place (DM or thread channel) and asker."""
    digest = hmac.new(_secret().encode(), f"raven:{place}:{user}".encode(), hashlib.sha256).digest()
    return str(uuid.UUID(bytes=digest[:16], version=4))


def session_url(session_id: str) -> str:
    return get_url(f"/copilot/chat/{session_id}")
