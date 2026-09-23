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

"""
FAC Chat Settings - Global configuration for FAC Chat.

Note: Models are now fetched from Assistant Runtime via the api.py module.
"""

from frappe.model.document import Document


class FACChatSettings(Document):
    """FAC Chat Settings - Global configuration for AR integration"""

    def before_save(self):
        from frappe_assistant_core.chat.tenant_credentials import preserve_tenant_secret_on_save

        preserve_tenant_secret_on_save(self)
