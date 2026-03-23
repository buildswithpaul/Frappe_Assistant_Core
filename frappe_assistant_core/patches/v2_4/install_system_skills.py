# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Migration patch to install system skills for existing sites.
"""

import frappe


def execute():
    """Install system skills from manifest."""
    from frappe_assistant_core.utils.migration_hooks import _install_system_skills

    _install_system_skills()
