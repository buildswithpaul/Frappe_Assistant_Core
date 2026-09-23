import unittest

from frappe_assistant_core.chat.api.block_builder import BlockBuilder


class TestBlockBuilderPlan(unittest.TestCase):
    def test_set_plan_creates_single_plan_block(self):
        bb = BlockBuilder()
        plan = {
            "id": "plan-1",
            "status": "running",
            "tasks": [{"id": "t1", "title": "A", "status": "pending"}],
        }
        bb.set_plan(plan)
        plan_blocks = [b for b in bb.blocks if b.get("type") == "plan"]
        self.assertEqual(len(plan_blocks), 1)
        self.assertEqual(plan_blocks[0]["tasks"][0]["title"], "A")

    def test_set_plan_replaces_not_appends(self):
        bb = BlockBuilder()
        bb.set_plan(
            {"id": "p", "status": "running", "tasks": [{"id": "t1", "title": "A", "status": "pending"}]}
        )
        bb.set_plan(
            {
                "id": "p",
                "status": "running",
                "tasks": [
                    {"id": "t1", "title": "A", "status": "done"},
                    {"id": "t2", "title": "B", "status": "running"},
                ],
            }
        )
        plan_blocks = [b for b in bb.blocks if b.get("type") == "plan"]
        self.assertEqual(len(plan_blocks), 1)
        self.assertEqual(plan_blocks[0]["tasks"][0]["status"], "done")
        self.assertEqual(len(plan_blocks[0]["tasks"]), 2)

    def test_set_plan_ignores_empty(self):
        bb = BlockBuilder()
        bb.set_plan({"id": "p", "status": "running", "tasks": []})
        self.assertEqual([b for b in bb.blocks if b.get("type") == "plan"], [])

    def test_plan_block_survives_snapshot(self):
        bb = BlockBuilder()
        bb.set_plan({"id": "p", "status": "running", "tasks": [{"id": "t1", "title": "A", "status": "done"}]})
        snap = bb.snapshot()
        self.assertTrue(any(b["type"] == "plan" for b in snap))
