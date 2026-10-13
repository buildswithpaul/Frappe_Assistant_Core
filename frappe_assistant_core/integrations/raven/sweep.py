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

"""Finish FAC Bot replies whose worker died mid-turn, so none is left streaming forever."""

import time

import frappe
from frappe.utils import escape_html

from frappe_assistant_core.integrations.raven import formatting
from frappe_assistant_core.integrations.raven.turn import REPLIES_KEY

QUIET_FOR = 600


def finish_interrupted_replies() -> int:
    """Every 5 minutes: a reply not edited for QUIET_FOR seconds lost its turn; say so on it."""
    finished = 0
    for reply, entry in (frappe.cache.hgetall(REPLIES_KEY) or {}).items():
        reply = reply.decode() if isinstance(reply, bytes) else reply
        if time.time() - entry["updated"] < QUIET_FOR:
            continue
        frappe.cache.hdel(REPLIES_KEY, reply)
        if not frappe.db.exists("Raven Message", reply):
            continue
        doc = frappe.get_doc("Raven Message", reply)
        doc.text = f"{doc.text or ''}<p><em>{escape_html(str(formatting.INTERRUPTED))}</em></p>"
        doc.flags.editing_metadata = True
        doc.save(ignore_permissions=True)
        finished += 1
    return finished
