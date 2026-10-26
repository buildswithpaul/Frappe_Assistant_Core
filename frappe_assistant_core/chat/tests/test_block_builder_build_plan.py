# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A build plan card is saved with its plan and with the decision the user made.

On reload FAC Chat draws the turn from the saved blocks, so the plan must survive in them
and the decision must read back as approved or as the feedback the user typed instead.
"""

from frappe_assistant_core.chat.api.block_builder import BlockBuilder
from frappe_assistant_core.tests.base_test import BaseAssistantTest

TOOL_ID = "toolu_plan"
PLAN_ID = "a" * 32
# The interrupt AR raises from propose_build_plan (assistant_runtime/agent/build_plan.py).
PLAN_INTERRUPT = {
    "id": "int-plan",
    "name": "propose_build_plan",
    "reason": {
        "type": "build_plan",
        "plan_id": PLAN_ID,
        "summary": "Add a region field to Customer and show it on a workspace.",
        "changes": [
            {
                "doctype": "Custom Field",
                "action": "create",
                "identity": {"dt": "Customer", "fieldname": "region"},
                "description": "Adds a Region field to Customer.",
                "goes_live": True,
            }
        ],
        "mockup_html": "<div class='mk-page'></div>",
    },
}


def _paused_builder() -> BlockBuilder:
    builder = BlockBuilder()
    builder.add_tool_call_start(TOOL_ID, "propose_build_plan", {"summary": "x", "changes": []})
    builder.add_approval_required(TOOL_ID, "propose_build_plan", {}, [PLAN_INTERRUPT])
    return builder


def _card(builder: BlockBuilder) -> dict:
    return next(b for b in builder.snapshot() if b["type"] == "interaction")


class TestBlockBuilderBuildPlan(BaseAssistantTest):
    def test_the_saved_card_keeps_the_whole_plan(self):
        card = _card(_paused_builder())
        self.assertEqual(card["interactionType"], "build_plan")
        self.assertEqual(card["interrupts"][0]["reason"], PLAN_INTERRUPT["reason"])

    def test_the_tool_row_is_internal(self):
        row = next(b for b in _paused_builder().snapshot() if b["type"] == "tool_call")
        self.assertTrue(row["isInternal"])

    def test_approving_the_plan_saves_it_as_approved(self):
        builder = _paused_builder()
        builder.resolve_pending_interactions(
            [{"interruptId": "int-plan", "response": {"decision": "approve", "plan_id": PLAN_ID}}]
        )
        self.assertEqual(_card(builder)["status"], "approved")

    def test_typed_feedback_saves_the_feedback_not_an_approval(self):
        builder = _paused_builder()
        builder.resolve_pending_interactions([{"interruptId": "int-plan", "response": "Use a Select field"}])
        card = _card(builder)
        self.assertEqual(card["status"], "answered")
        self.assertEqual(card["userResponse"], "Use a Select field")
