# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""FAC Tool Role Access child table for role-based tool access control."""

from frappe.model.document import Document


class FACToolRoleAccess(Document):
    """
    Child table for FAC Tool Configuration role-based access.

    Fields:
        role: Link to Role DocType
        allow_access: Whether this role has access (default: 1)
    """

    pass
