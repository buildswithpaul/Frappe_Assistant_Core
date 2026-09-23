import inspect
import unittest


class TestRelayHandlesWorkflowCreated(unittest.TestCase):
    """A new AR SSE event type must be registered in BOTH relay loops
    (main + resume) or it is silently dropped — never emitted to the
    browser and never persisted as a block. This is the exact class of
    bug that shipped: workflow_created was emitted by AR but unknown to
    the FAC relay. These guard both loops against that drift.
    """

    def test_main_loop_handles_workflow_created(self):
        from frappe_assistant_core.chat.api.chat import relay

        source = inspect.getsource(relay._relay_ar_stream)
        self.assertIn('event_type == "workflow_created"', source)
        self.assertIn("add_workflow_created", source)

    def test_resume_loop_handles_workflow_created(self):
        from frappe_assistant_core.chat.api.chat import relay

        source = inspect.getsource(relay._relay_ar_interrupt_resume)
        self.assertIn('event_type == "workflow_created"', source)
        self.assertIn("add_workflow_created", source)


if __name__ == "__main__":
    unittest.main()
