# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
What tools/list tells an AR caller about tool packs: the catalogue of packs present in
this listing and the packs the conversation's attachments already call for.
"""

from collections.abc import Iterable
from pathlib import PurePath

from frappe_assistant_core.core.tool_packs import ToolPack


def pack_map(packs: Iterable[ToolPack]) -> dict[str, str]:
    """``{tool_name: pack_id}``, built once per request."""
    return {tool: pack.id for pack in packs for tool in pack.tools}


def catalogue(packs: Iterable[ToolPack], listed_tools: Iterable[str]) -> list[dict]:
    """Packs as AR reads them, each narrowed to the tools this caller is actually listed.

    A pack with none of its tools listed (app not installed, role-filtered, FAC-Cloud-only)
    is omitted, so AR never offers a pack it cannot deliver.
    """
    listed = set(listed_tools)
    entries = []
    for pack in packs:
        tools = [tool for tool in pack.tools if tool in listed]
        if not tools:
            continue
        entries.append(
            {
                "id": pack.id,
                "title": pack.title,
                "description": pack.description,
                "tools": tools,
                "file_types": list(pack.file_types),
                "skills": list(pack.skills),
            }
        )
    return entries


def wanted_packs(session_id: str, user: str, packs: Iterable[ToolPack]) -> list[str]:
    """Ids of packs whose ``file_types`` match a file attached in this conversation."""
    from frappe_assistant_core.chat.api.chat.conversation_files import _conversation_files

    files = _conversation_files(session_id, user)
    extensions = {PurePath(f.get("file_name") or "").suffix.lstrip(".").lower() for f in files}
    extensions.discard("")
    if not extensions:
        return []
    return [pack.id for pack in packs if extensions.intersection(pack.file_types)]
