import unittest

from frappe_assistant_core.chat.api.block_builder import BlockBuilder

_EVENT = {
    "workflow_name": "Weekly Overdue Invoice Chaser",
    "docname": "WF-00049",
    "link": "/copilot/agents/WF-00049",
    "status": "Draft",
    "action": "created",
}


class TestBlockBuilderWorkflowCreated(unittest.TestCase):
    def test_appends_a_durable_workflow_created_block(self):
        bb = BlockBuilder()
        bb.add_workflow_created(_EVENT)
        blocks = [b for b in bb.blocks if b.get("type") == "workflow_created"]
        self.assertEqual(len(blocks), 1)
        b = blocks[0]
        self.assertEqual(b["docname"], "WF-00049")
        self.assertEqual(b["workflow_name"], "Weekly Overdue Invoice Chaser")
        self.assertEqual(b["link"], "/copilot/agents/WF-00049")
        self.assertEqual(b["status"], "Draft")
        self.assertEqual(b["action"], "created")
        self.assertTrue(b["id"])

    def test_appends_not_replaces_across_multiple_events(self):
        bb = BlockBuilder()
        bb.add_workflow_created(_EVENT)
        bb.add_workflow_created({**_EVENT, "docname": "WF-00050", "action": "updated"})
        blocks = [b for b in bb.blocks if b.get("type") == "workflow_created"]
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[1]["action"], "updated")
        self.assertEqual(blocks[1]["docname"], "WF-00050")

    def test_ignores_event_without_docname(self):
        bb = BlockBuilder()
        bb.add_workflow_created({"workflow_name": "X"})
        self.assertEqual([b for b in bb.blocks if b.get("type") == "workflow_created"], [])


if __name__ == "__main__":
    unittest.main()
