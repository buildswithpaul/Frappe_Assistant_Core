# Frappe Assistant Core - Block Builder
# Copyright (C) 2025 Paul Clinton
#
# This program is proprietary and confidential.

"""
BlockBuilder — Accumulates streaming events and produces a blocks snapshot.

Mirrors the frontend's blockHandlers.js logic on the server side. During
streaming, the FACO relay thread feeds events into BlockBuilder. At
stream_complete, the snapshot is persisted on the FACO Message so the
frontend can render it directly on page refresh — no event reconstruction.

For HITL resume, the builder is initialized with the existing blocks from
the previous stream, pending interactions are resolved, and new blocks are
appended on top.
"""

import copy
import json
import uuid
from datetime import datetime, timezone
from typing import Any

# Tools whose execution is internal plumbing — rendered as slim indicators,
# not full expandable cards. Must match frontend's INTERNAL_TOOLS set.
INTERNAL_TOOLS = frozenset(
    {
        "get_skill",
        "workspace_read_file",
        "workspace_write_file",
        "workspace_list_files",
        "workspace_delete_file",
        "ask_user",
    }
)

MAX_EMIT_RESULT_CHARS = 8000
_TRUNCATION_SUFFIX = "\n\n…[truncated — full result available on reload]"
# Keys that drive client-side rendering (tool_call block result + generated-document
# footer). Never truncate these — the socket copy must stay renderable.
_STRUCTURAL_RESULT_KEYS = frozenset(
    {
        "success",
        "file_url",
        "file_name",
        "file_size_display",
        "document_type",
        "status",
        "message",
        "error",
    }
)


def _generate_id(prefix: str = "block") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate_str(value: str) -> str:
    if len(value) <= MAX_EMIT_RESULT_CHARS:
        return value
    return value[:MAX_EMIT_RESULT_CHARS] + _TRUNCATION_SUFFIX


def truncate_result_for_emit(result: Any) -> Any:
    """Bound the size of a tool result BEFORE it is emitted over Socket.IO.

    A large single frame delays the client's engine.io PONG past the ping
    timeout and drops the socket. This caps the emitted copy only — the
    PERSISTED block keeps the full result, so a reload / reconnect re-read
    renders the complete output. Structural keys are preserved verbatim.
    """
    if isinstance(result, str):
        return _truncate_str(result)

    if isinstance(result, dict):
        out = {}
        for key, value in result.items():
            if key in _STRUCTURAL_RESULT_KEYS:
                out[key] = value
            elif isinstance(value, str):
                out[key] = _truncate_str(value)
            else:
                out[key] = value
        return out

    if isinstance(result, list):
        try:
            serialized = json.dumps(result, default=str)
        except (TypeError, ValueError):
            serialized = repr(result)
        if len(serialized) > MAX_EMIT_RESULT_CHARS:
            return {
                "_truncated": True,
                "preview": serialized[:MAX_EMIT_RESULT_CHARS],
                "_note": "full result available on reload",
            }
        return result

    return result


class BlockBuilder:
    """Accumulates streaming events and produces a blocks snapshot."""

    def __init__(self, existing_blocks: list[dict] | None = None):
        """
        Initialize with optional existing blocks for HITL resume.

        Args:
            existing_blocks: Blocks from the previous stream(s). On resume,
                these are loaded from the FACO Message and new blocks are
                appended after resolving pending interactions.
        """
        self.blocks: list[dict] = copy.deepcopy(existing_blocks) if existing_blocks else []
        self._ask_user_tool_ids: set[str] = set()
        self._active_thinking_id: str | None = None

        # Rebuild _ask_user_tool_ids from existing blocks (for resume)
        for block in self.blocks:
            if block.get("type") == "interaction" and block.get("tool_name") == "ask_user":
                self._ask_user_tool_ids.add(block.get("id", ""))

    def add_thinking(self, content: str) -> None:
        """Add or append to a thinking block."""
        if self._active_thinking_id:
            for block in reversed(self.blocks):
                if block.get("id") == self._active_thinking_id:
                    block["content"] = (block.get("content") or "") + content
                    return
        # New thinking block
        block_id = _generate_id("thinking")
        self._active_thinking_id = block_id
        self.blocks.append(
            {
                "type": "thinking",
                "id": block_id,
                "content": content,
                "isExpanded": False,
                "isStreaming": False,
                "startTime": _now_iso(),
            }
        )

    def complete_thinking(self) -> None:
        """Mark the current thinking block as complete."""
        if self._active_thinking_id:
            for block in reversed(self.blocks):
                if block.get("id") == self._active_thinking_id:
                    block["endTime"] = _now_iso()
                    break
            self._active_thinking_id = None

    def add_tool_call_start(self, tool_id: str, tool_name: str, tool_input: dict) -> None:
        """Add a tool call start block."""
        self._close_thinking()

        # ask_user: the approval_required creates the interaction block instead
        if tool_name == "ask_user":
            self._ask_user_tool_ids.add(tool_id)
            return

        self.blocks.append(
            {
                "type": "tool_call",
                "id": tool_id,
                "tool_name": tool_name,
                "input": tool_input or {},
                "status": "running",
                "result": None,
                "isExpanded": False,
                "isInternal": tool_name in INTERNAL_TOOLS,
                "startTime": _now_iso(),
                "endTime": None,
            }
        )

    def add_tool_call_result(
        self,
        tool_id: str,
        result: Any,
        status: str = "success",
        duration_ms: int | None = None,
        tool_name: str | None = None,
    ) -> None:
        """Update a tool call block with its result, or set userResponse on an ask_user interaction."""
        # ask_user result → set userResponse on the interaction block
        if tool_id in self._ask_user_tool_ids:
            for block in reversed(self.blocks):
                if block.get("type") == "interaction" and block.get("id") == tool_id:
                    block["userResponse"] = _extract_text_result(result)
                    block["status"] = "answered"
                    break
            return

        # Regular tool result → update the tool_call block
        resolved_tool_name = tool_name
        for block in reversed(self.blocks):
            if block.get("type") == "tool_call" and block.get("id") == tool_id:
                block["status"] = status
                block["result"] = result
                block["endTime"] = _now_iso()
                if duration_ms is not None:
                    block["duration_ms"] = duration_ms
                resolved_tool_name = resolved_tool_name or block.get("tool_name")
                break

        # Side effect: surface PDFs from the generate_document tool in a
        # dedicated footer block. Mirrors blockHandlers.js so the persisted
        # snapshot matches what the live UI renders during streaming.
        if status == "success" and resolved_tool_name == "generate_document":
            self._maybe_attach_generated_document(result)

    def _maybe_attach_generated_document(self, result: Any) -> None:
        if not isinstance(result, dict):
            return
        if result.get("success") is not True:
            return
        file_url = result.get("file_url")
        if not file_url:
            return
        block = next(
            (b for b in self.blocks if b.get("type") == "generated_documents"),
            None,
        )
        if block is None:
            block = {
                "type": "generated_documents",
                "id": _generate_id("generated_documents"),
                "items": [],
                "timestamp": _now_iso(),
            }
            self.blocks.append(block)
        items: list[dict] = block.setdefault("items", [])
        if any(item.get("file_url") == file_url for item in items):
            return
        items.append(
            {
                "file_url": file_url,
                "file_name": result.get("file_name"),
                "file_size_display": result.get("file_size_display") or "",
                "document_type": "PDF",
            }
        )

    def add_tool_cancelled(self, tool_id: str, message: str = "Cancelled") -> None:
        """Mark a tool call as cancelled."""
        for block in reversed(self.blocks):
            if block.get("id") == tool_id:
                block["status"] = "cancelled"
                block["result"] = {"message": message}
                block["endTime"] = _now_iso()
                break

    def add_approval_required(
        self,
        tool_id: str,
        tool_name: str,
        tool_input: dict,
        interrupts: list[dict],
    ) -> None:
        """Add an interaction block for HITL approval or question."""
        self._close_thinking()

        reason = interrupts[0].get("reason", {}) if interrupts else {}
        interaction_type = reason.get("type", "approval")

        self.blocks.append(
            {
                "type": "interaction",
                "id": tool_id,
                "interactionType": interaction_type,
                "tool_name": tool_name or "",
                "input": tool_input or {},
                "question": reason.get("question") or reason.get("action", ""),
                "options": reason.get("options", []),
                "description": reason.get("description"),
                "interrupts": interrupts,
                "action": reason.get("action") or reason.get("question", ""),
                "status": "pending",
                "isExpanded": False,
                "startTime": _now_iso(),
            }
        )

    def add_text(self, content: str) -> None:
        """Add text content, merging consecutive text into one block."""
        self._close_thinking()
        if not content:
            return

        # Merge with previous text block if it's the last block
        if self.blocks:
            last = self.blocks[-1]
            if last.get("type") == "text":
                last["content"] = (last.get("content") or "") + content
                return

        self.blocks.append(
            {
                "type": "text",
                "id": _generate_id("text"),
                "content": content,
            }
        )

    def add_workflow_created(self, data: dict) -> None:
        """Append a workflow-created action card (an "Open in builder" button).

        Emitted by the chat workflow-builder tools after a Draft workflow is
        created/updated. Each event is a distinct action, so we append rather
        than replace.
        """
        if not data or not data.get("docname"):
            return
        self.blocks.append(
            {
                "type": "workflow_created",
                "id": _generate_id("workflow_created"),
                "workflow_name": data.get("workflow_name"),
                "docname": data.get("docname"),
                "link": data.get("link"),
                "status": data.get("status"),
                "action": data.get("action"),
            }
        )

    def add_sources(self, sources: list[dict]) -> None:
        """Attach (or replace) the RAG citation sources block for this turn.

        Idempotent — a second call with the same session overwrites the first
        so that a HITL resume with a new retrieval doesn't accumulate duplicate
        footers. Empty or falsy ``sources`` removes the block.
        """
        # Remove any existing sources block (last-writer-wins)
        self.blocks = [b for b in self.blocks if b.get("type") != "sources"]
        if not sources:
            return
        self.blocks.append(
            {
                "type": "sources",
                "id": _generate_id("sources"),
                "items": sources,
                "timestamp": _now_iso(),
            }
        )

    def set_plan(self, plan: dict) -> None:
        """Set (replace) the task-plan block. Last-writer-wins on the full plan.

        AR sends the full authoritative plan with each plan event, so we
        replace the existing plan block wholesale — no per-task merge.
        """
        if not plan or not plan.get("tasks"):
            return
        block = {
            "type": "plan",
            "id": plan.get("id") or _generate_id("plan"),
            "status": plan.get("status", "running"),
            "tasks": plan.get("tasks", []),
        }
        for i, existing in enumerate(self.blocks):
            if existing.get("type") == "plan":
                self.blocks[i] = block
                return
        self.blocks.insert(0, block)

    def finalize_sources(self) -> None:
        """Drop the sources block if uncited, otherwise move it to the end.

        Called at stream_complete before persistence. Two jobs:

        1. **Drop-if-uncited.** If the assistant's final text contains no
           ``[N]`` markers, the retrieved sources weren't actually used —
           showing a "Sources" footer would imply grounding that isn't there.
        2. **Reorder-to-end.** The ``sources`` SSE event arrives before the
           first text chunk (per the streaming.py pipeline), so ``add_sources``
           lands the sources block at index 0. The UI renders blocks in
           array order, so without reordering the footer would sit ABOVE
           the answer. Move sources to the end so it reads as a footer.
        """
        import re

        has_sources_block = any(b.get("type") == "sources" for b in self.blocks)
        if not has_sources_block:
            return
        text_content = "".join(b.get("content", "") for b in self.blocks if b.get("type") == "text")
        if not re.search(r"\[\d+\]", text_content):
            self.blocks = [b for b in self.blocks if b.get("type") != "sources"]
            return
        sources_blocks = [b for b in self.blocks if b.get("type") == "sources"]
        other_blocks = [b for b in self.blocks if b.get("type") != "sources"]
        self.blocks = other_blocks + sources_blocks

    def resolve_pending_interactions(self, interrupt_responses: list[dict]) -> None:
        """
        Resolve pending interaction blocks at the start of a HITL resume.

        Called with the user's interrupt_response array. Each response has:
        {"interruptId": str, "response": "approve"|"rejected"|"trust"|<user_answer>}
        """
        if not interrupt_responses:
            return

        # Build lookup: interrupt_id → response
        response_map = {}
        for resp in interrupt_responses:
            response_map[resp.get("interruptId", "")] = resp.get("response", "approve")

        for block in self.blocks:
            if block.get("type") != "interaction" or block.get("status") != "pending":
                continue

            # Match by interrupt ID from the block's interrupts array
            block_interrupts = block.get("interrupts", [])
            for interrupt in block_interrupts:
                interrupt_id = interrupt.get("id", "")
                if interrupt_id in response_map:
                    user_response = response_map[interrupt_id]
                    reason = interrupt.get("reason", {})
                    interaction_type = reason.get("type", "approval")

                    if interaction_type == "approval":
                        if user_response in ("approve", "trust", "session"):
                            block["status"] = "approved"
                        else:
                            block["status"] = "rejected"
                    else:
                        # Question types — store the user's answer
                        block["status"] = "answered"
                        block["userResponse"] = user_response
                    break

    def snapshot(self) -> list[dict]:
        """Return a deep copy of the blocks array for persistence."""
        return copy.deepcopy(self.blocks)

    def _close_thinking(self) -> None:
        """Close any active thinking block."""
        if self._active_thinking_id:
            self.complete_thinking()


def _extract_text_result(result: Any) -> str | None:
    """Extract displayable text from a tool result."""
    if result is None:
        return None
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        # Strands format: [{"text": "..."}, ...]
        texts = []
        for item in result:
            if isinstance(item, dict) and "text" in item:
                texts.append(item["text"])
        return ", ".join(texts) if texts else str(result)
    return str(result)
