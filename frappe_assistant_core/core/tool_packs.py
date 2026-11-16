# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Tool packs: named groups of tools a plugin declares so a client can ask for only the
groups a conversation needs. A tool in no pack belongs to the base set, always sent.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolPack:
    """A group of tools that are loaded together on demand."""

    id: str
    title: str
    description: str
    tools: tuple[str, ...]
    # Attachment extensions that signal the conversation needs this pack.
    file_types: tuple[str, ...] = ()
    # Ids of the FAC Skill records (FAC Skill.skill_id) that go with this pack.
    skills: tuple[str, ...] = ()
