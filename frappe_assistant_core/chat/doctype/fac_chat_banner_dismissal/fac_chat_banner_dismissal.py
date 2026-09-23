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

from frappe.model.document import Document


class FACChatBannerDismissal(Document):
    """Records that a user has dismissed the FAC Chat discovery banner.

    One row per user (autoname = field:user). Once a row exists, the banner
    is never re-shown to that user, even if FAC Chat is later toggled off
    and back on. The `dismissed_on` field captures the timestamp for
    analytics / audit purposes.
    """

    pass
