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
Agent Skills rendering for the MCP skills extension: name rules, the SKILL.md bytes and the
manifest entry. The digest in an entry is computed from the same bytes a read serves.
"""

import hashlib
import re
from collections.abc import Callable

import frappe
import yaml
from frappe import _

from frappe_assistant_core.api.handlers.resources import SkillManager
from frappe_assistant_core.mcp.protocol import ERR_INVALID_PARAMS, ProtocolError

SKILL_URI = "skill://{skill_id}/SKILL.md"

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024

_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_SKILL_URI_PATTERN = re.compile(r"^skill://([^/]+)/SKILL\.md$")
_SKILL_SCHEME = "skill://"
_FAC_SKILL_PREFIX = "fac://skills/"
_LISTED_SKILL_TYPE = "Workflow"


def is_valid_skill_name(skill_id: str) -> bool:
    """True when skill_id is a valid Agent Skills name."""
    return bool(skill_id) and len(skill_id) <= MAX_NAME_LENGTH and _NAME_PATTERN.match(skill_id) is not None


def is_valid_description(description: str) -> bool:
    """True when description fits the Agent Skills 1-1024 character limit."""
    return 1 <= len(description or "") <= MAX_DESCRIPTION_LENGTH


def is_listable(skill: dict) -> bool:
    """True when a skill row can be advertised to MCP clients."""
    return is_valid_skill_name(skill.get("skill_id") or "") and is_valid_description(
        _one_line(skill.get("description") or "")
    )


def _one_line(text: str) -> str:
    """Collapse every run of whitespace, newlines included, to one space.

    Clients read the frontmatter line by line (the TS SDK's built-in parser refuses a value that
    spans lines), and FAC Skill.description is Small Text, so a stored newline must not survive.
    """
    return " ".join(text.split())


def _frontmatter(skill_id: str, description: str) -> dict:
    """The frontmatter values, identical in the SKILL.md bytes and the manifest entry."""
    return {"name": skill_id, "description": _one_line(description)}


def render_skill_md(skill_id: str, description: str, content: str) -> bytes:
    """Render the SKILL.md bytes: YAML frontmatter, a blank line, then the content.

    One line per key: width=inf stops PyYAML folding a long value, and any value plain YAML
    cannot hold on one line (": ", a leading "#", yes/null) is single-line quoted, which the
    TS SDK parser unquotes.
    """
    frontmatter = yaml.safe_dump(
        _frontmatter(skill_id, description), sort_keys=False, allow_unicode=True, width=float("inf")
    )
    return f"---\n{frontmatter}---\n\n{content}".encode()


def skill_entry(skill_id: str, description: str, content: str) -> dict:
    """Build the skills/list entry for one skill."""
    raw = render_skill_md(skill_id, description, content)
    uri = SKILL_URI.format(skill_id=skill_id)
    return {
        "uri": uri,
        "frontmatter": _frontmatter(skill_id, description),
        "resources": [{"uri": uri, "digest": "sha256:" + hashlib.sha256(raw).hexdigest(), "size": len(raw)}],
    }


def _unknown_skill(uri: str, skill_id: str) -> ProtocolError:
    """The one answer for a skill that is missing, malformed or not the caller's to read."""
    return ProtocolError(400, ERR_INVALID_PARAMS, _("Skill not found: {0}").format(skill_id), {"uri": uri})


def _skill_id_of(uri: str) -> str | None:
    match = _SKILL_URI_PATTERN.match(uri) if isinstance(uri, str) else None
    return match.group(1) if match else None


def _accessible_skill(uri: str) -> dict:
    """The row behind a skill:// URI, or ProtocolError when the caller cannot know about it."""
    skill_id = _skill_id_of(uri)
    skill = SkillManager().get_accessible_skill(skill_id) if skill_id else None
    if not skill or not is_listable(skill):
        raise _unknown_skill(uri, skill_id or str(uri))
    return skill


def handle_skills_list(params: dict) -> dict:
    """skills/list: the Published Workflow skills the caller can read, all of them, unpaginated."""
    manager = SkillManager()
    candidates = [
        skill
        for skill in manager.get_user_accessible_skills()
        if skill.status == "Published" and skill.skill_type == _LISTED_SKILL_TYPE
    ]
    listable = []
    for skill in candidates:
        if is_listable(skill):
            listable.append(skill)
        else:
            frappe.logger("mcp_skills").debug(f"Skill {skill.skill_id!r} is not a valid Agent Skills entry")
    contents = {
        row.name: row.content or ""
        for row in frappe.get_all(
            "FAC Skill", filters={"name": ["in", [s.name for s in listable]]}, fields=["name", "content"]
        )
    }
    return {"skills": [skill_entry(s.skill_id, s.description, contents.get(s.name, "")) for s in listable]}


def handle_skills_get(params: dict) -> dict:
    """skills/get: one entry for any accessible Published skill, whatever its type."""
    skill = _accessible_skill(params.get("uri"))
    return {"skill": skill_entry(skill["skill_id"], skill["description"], skill["content"])}


def read_skill_resource(uri: str) -> dict:
    """resources/read for skill://<id>/SKILL.md: the same bytes the manifest digest was taken over."""
    skill = _accessible_skill(uri)
    try:
        content = SkillManager().read_skill_content(skill["skill_id"])
    except frappe.PermissionError:
        raise _unknown_skill(uri, skill["skill_id"]) from None
    if content is None:
        raise _unknown_skill(uri, skill["skill_id"])
    raw = render_skill_md(skill["skill_id"], skill["description"], content)
    return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": raw.decode("utf-8")}]}


def read_resource(params: dict, read_fac_resource: Callable[[dict], dict]) -> dict:
    """resources/read: unchanged on the handshake era. On the modern era skill:// is served here and
    everything else through read_fac_resource, and a skill the caller may not read answers exactly
    as one that does not exist.
    """
    if frappe.local.mcp_era != "modern":
        return read_fac_resource(params)
    uri = params.get("uri", "")
    if uri.startswith(_SKILL_SCHEME):
        return read_skill_resource(uri)
    try:
        return read_fac_resource(params)
    except ValueError as e:
        raise ProtocolError(400, ERR_INVALID_PARAMS, str(e), {"uri": uri}) from None
    except frappe.PermissionError:
        raise _unknown_skill(uri, uri.removeprefix(_FAC_SKILL_PREFIX)) from None


MODERN_METHODS = {"skills/list": handle_skills_list, "skills/get": handle_skills_get}
