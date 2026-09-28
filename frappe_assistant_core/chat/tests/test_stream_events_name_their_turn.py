# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Every stream event names its turn.

stream_start, stream_aborted and stream_error carried the turn's message_id,
but stream_chunk, stream_complete and the other per-turn events did not. A
conversation's turns share one socket room, so a client could not tell which
turn a chunk or a completion belonged to: after a Stop, the stopped turn's
late events could land on the next turn's live bubble. Every payload the
relay emits now carries ``message_id``: the id AR's stream_start gave the
turn, and None until the relay has handled that stream_start.

Drives both relay loops over a fake SDK stream against real FAC Chat Message
rows owned by a throwaway user, rolled back with the class. The worker-thread
Frappe context, the cancel flag, the socket and the quota cache are stubbed.
"""

import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api.chat import relay
from frappe_assistant_core.tests.base_test import BaseAssistantTest

NO_KEY = "<no message_id key>"
QUESTION = "Which invoices are overdue?"
PAUSED_TEXT = "I will create the ToDo once you approve."
PENDING_CARD = {
    "type": "interaction",
    "id": "toolu_0",
    "interactionType": "approval",
    "tool_name": "create_document",
    "interrupts": [{"id": "int-1", "name": "create_document", "reason": {"type": "approval"}}],
    "status": "pending",
}
PLAN = {
    "id": "plan-1",
    "status": "running",
    "tasks": [{"id": "t1", "title": "Find the overdue invoices", "status": "running"}],
}


def _event(name: str, **data) -> dict:
    return {"event": name, "data": data}


def _named_events(message_id: str) -> list[dict]:
    """AR's events after its stream_start, in AR's order (context_summarized
    follows stream_complete). The relay forwards each under its own name."""
    return [
        _event("model_selected", mode="auto", selected="m", routing={"selected_model": "m"}),
        _event("routing_notice", code="downgraded_for_credits", tier_used="Economy", tier_wanted="Premium"),
        _event("sources", message_id=message_id, sources=[{"index": 1, "title": "Credit policy"}]),
        _event("task_updated", plan=PLAN),
        _event("thinking", content="Checking the ledger."),
        _event("thinking_complete"),
        _event("heartbeat"),
        _event("stream_chunk", content="Two are overdue."),
        _event(
            "tool_call_start",
            tool_id="toolu_1",
            tool_name="list_documents",
            input={"doctype": "Sales Invoice"},
        ),
        _event(
            "tool_call_result",
            tool_id="toolu_1",
            tool_name="list_documents",
            result={"success": True},
            status="success",
        ),
        _event("tool_cancelled", tool_id="toolu_2", tool_name="send_email", message="Cancelled"),
        _event(
            "workflow_created",
            workflow_name="Overdue reminder",
            docname="WF-0001",
            status="Draft",
            action="created",
        ),
        _event(
            "approval_required",
            tool_id="toolu_3",
            tool_name="create_document",
            input={"doctype": "ToDo"},
            interrupts=[{"id": "int-2", "name": "create_document", "reason": {"type": "approval"}}],
        ),
        _event("stream_complete", full_response="Two are overdue.", credits_used=2, model="m"),
        _event("context_summarized", message="Older messages were summarized."),
    ]


def _named(message_id: str) -> list[tuple]:
    return [(event["event"], message_id) for event in _named_events(message_id)]


def _ids(emitted: list[dict]) -> list[tuple]:
    """Each payload's event, and the turn it names (NO_KEY when it has no key)."""
    return [(payload["event"], payload.get("message_id", NO_KEY)) for payload in emitted]


class TestEveryStreamEventNamesItsTurn(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("turn-ids")
        frappe.set_user(self.user)
        self.sid = f"turn-ids-{frappe.generate_hash(length=8)}"

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _relay(self, relay_loop, events, **kwargs) -> list[dict]:
        """Run ``relay_loop`` over AR ``events``; return the socket payloads it emitted."""
        client = MagicMock()
        client.stream_chat.return_value = iter(events)
        emitted = []
        with ExitStack() as stack:
            enter = stack.enter_context
            enter(
                patch(
                    "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
                    return_value=client,
                )
            )
            # The relay opens and tears down a worker-thread Frappe context; here it
            # runs inside the test's. set_user is stubbed because the real one resets
            # the running session.
            for name in ("init", "connect", "set_user", "destroy"):
                enter(patch(f"frappe.{name}"))
            enter(patch.object(relay, "is_cancelled", return_value=False))
            enter(patch.object(relay, "_update_subscription_cache"))
            enter(
                patch(
                    "frappe_assistant_core.chat.quota_cache.get_quota_snapshot",
                    return_value={"quota_used": 0, "quota_total": 100},
                )
            )
            enter(
                patch.object(
                    relay, "_emit_socket_event", side_effect=lambda _sid, payload: emitted.append(payload)
                )
            )
            relay_loop(session_id=self.sid, user=self.user, site=frappe.local.site, **kwargs)
        return emitted

    def test_the_send_loop_names_its_turn_on_every_event(self):
        emitted = self._relay(
            relay._relay_ar_stream,
            [
                _event("heartbeat"),  # a keepalive AR sent before its stream_start
                _event("stream_start", message_id="msg-new", zero_retention=False),
                *_named_events("msg-new"),
            ],
            full_prompt=QUESTION,
            original_message=QUESTION,
            context=None,
            message_name=None,
        )

        # The first stream_start is the relay's own, sent before it calls AR.
        self.assertEqual(
            _ids(emitted),
            [("stream_start", None), ("heartbeat", None), ("stream_start", "msg-new"), *_named("msg-new")],
        )

    def test_the_resume_loop_names_its_turn_on_every_event(self):
        frappe.get_doc(
            {
                "doctype": "FAC Chat Message",
                "session_id": self.sid,
                "message_id": "msg-paused",
                "user": self.user,
                "role": "assistant",
                "content": PAUSED_TEXT,
                "blocks": json.dumps(
                    [{"type": "text", "id": "text-1", "content": PAUSED_TEXT}, PENDING_CARD]
                ),
            }
        ).insert(ignore_permissions=True)

        emitted = self._relay(
            relay._relay_ar_interrupt_resume,
            [
                _event("heartbeat"),
                _event("stream_start", message_id="msg-paused", resumed=True, zero_retention=False),
                *_named_events("msg-paused"),
            ],
            interrupt_response=[{"interruptId": "int-1", "response": "approve"}],
            message_id="msg-paused",
        )

        self.assertEqual(
            _ids(emitted),
            [("heartbeat", None), ("stream_start", "msg-paused"), *_named("msg-paused")],
        )
