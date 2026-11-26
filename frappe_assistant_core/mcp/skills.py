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

"""
Agent Skills rendering for the MCP skills extension: name rules, the SKILL.md bytes and the
manifest entry. The digest in an entry is computed from the same bytes a read serves.
"""

import hashlib
import re

import yaml

SKILL_URI = "skill://{skill_id}/SKILL.md"

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024

_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def is_valid_skill_name(skill_id: str) -> bool:
    """True when skill_id is a valid Agent Skills name."""
    return bool(skill_id) and len(skill_id) <= MAX_NAME_LENGTH and _NAME_PATTERN.match(skill_id) is not None


def is_valid_description(description: str) -> bool:
    """True when description fits the Agent Skills 1-1024 character limit."""
    return 1 <= len(description or "") <= MAX_DESCRIPTION_LENGTH


def is_listable(skill: dict) -> bool:
    """True when a skill row can be advertised to MCP clients."""
    return is_valid_skill_name(skill.get("skill_id") or "") and is_valid_description(
        skill.get("description") or ""
    )


def render_skill_md(skill_id: str, description: str, content: str) -> bytes:
    """Render the SKILL.md bytes: YAML frontmatter, a blank line, then the content."""
    frontmatter = yaml.safe_dump(
        {"name": skill_id, "description": description}, sort_keys=False, allow_unicode=True
    )
    return f"---\n{frontmatter}---\n\n{content}".encode()


def skill_entry(skill_id: str, description: str, content: str) -> dict:
    """Build the skills/list entry for one skill."""
    raw = render_skill_md(skill_id, description, content)
    uri = SKILL_URI.format(skill_id=skill_id)
    return {
        "uri": uri,
        "frontmatter": {"name": skill_id, "description": description},
        "resources": [{"uri": uri, "digest": "sha256:" + hashlib.sha256(raw).hexdigest(), "size": len(raw)}],
    }
