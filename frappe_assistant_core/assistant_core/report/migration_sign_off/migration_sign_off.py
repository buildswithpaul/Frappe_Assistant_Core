# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Migration Sign-off (#33999): what a data migration brought in, for the business to sign off.
The numbers are counted in import_signoff, from the files and from ERPNext."""

from frappe_assistant_core.utils import import_signoff


def execute(filters=None):
    return import_signoff.execute(filters)
