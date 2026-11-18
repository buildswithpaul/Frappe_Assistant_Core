# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""FAC Tool User Access child table: users given a tool restricted to listed roles and users."""

from frappe.model.document import Document


class FACToolUserAccess(Document):
    """
    Child table for FAC Tool Configuration user access.

    Fields:
        user: Link to User DocType
        allow_access: Whether this user has access (default: 1)
    """

    pass
