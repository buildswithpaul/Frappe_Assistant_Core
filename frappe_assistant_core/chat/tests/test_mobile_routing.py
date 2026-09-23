"""The mobile surface carries the receipt too — including on a free turn."""

import inspect
import unittest

from frappe_assistant_core.chat.api import mobile_stream


class TestMobileRoutingWiring(unittest.TestCase):
    def test_stream_complete_sends_the_receipt_and_the_model(self):
        src = inspect.getsource(mobile_stream)
        at = src.index('_format_sse_event(\n                    "stream_complete"')
        window = src[at : at + 900]
        self.assertIn('"routing"', window)
        self.assertIn('"model_id"', window)

    def test_the_conversation_log_persists_the_receipt(self):
        sig = inspect.signature(mobile_stream._log_conversation)
        self.assertIn("routing", sig.parameters)
        src = inspect.getsource(mobile_stream._log_conversation)
        self.assertIn('"routing": routing', src)

    def test_history_selects_the_routing_column(self):
        src = inspect.getsource(mobile_stream)
        self.assertIn('"credits_used", "routing"', src.replace("'", '"'))

    def test_a_zero_credit_turn_still_returns_its_receipt(self):
        # `if msg.model or msg.credits_used:` returns metadata None on any
        # cached, errored or free turn — dropping a receipt that is present.
        # Same class of conditional-guard drop as the MessageBubble footer.
        src = inspect.getsource(mobile_stream)
        self.assertIn("if msg.model or msg.credits_used or msg.routing:", src)

    def test_the_metadata_dict_carries_the_receipt(self):
        src = inspect.getsource(mobile_stream)
        at = src.index("if msg.model or msg.credits_used or msg.routing:")
        self.assertIn('"routing"', src[at : at + 400])


if __name__ == "__main__":
    unittest.main()
