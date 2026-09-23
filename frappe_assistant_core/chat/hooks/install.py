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

"""FAC Chat — after_install hook.

Seeds FAC Chat Settings defaults on a fresh install so the Form UI reflects
the correct values immediately without requiring the admin to save once.
Mirrors the ERPNext single-DocType install pattern (schema default + explicit
set_single_value so the row exists in the DB immediately).
"""

import frappe

from frappe_assistant_core.chat.cloud_url import sync_cloud_url_mirror


def after_install() -> None:
    """Seed FAC Chat Settings defaults on fresh install."""
    _seed_fac_cloud_url()


def _seed_fac_cloud_url() -> None:
    try:
        sync_cloud_url_mirror()
    except Exception:
        # FAC Chat Settings table may not exist yet during a partial migration.
        pass
