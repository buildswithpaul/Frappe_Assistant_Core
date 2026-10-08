import re
from pathlib import Path

from frappe_assistant_core.chat.api.block_builder import INTERNAL_TOOLS, BlockBuilder
from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT_LIST = Path(__file__).resolve().parents[1] / "frontend" / "src" / "utils" / "internalTools.js"


class TestBlockBuilderInternalTools(BaseAssistantTest):
    def test_delegate_is_persisted_as_internal(self):
        # The plan rail represents delegated work; a reloaded turn must not
        # also draw `delegate` as a tool row in the timeline.
        bb = BlockBuilder()
        bb.add_tool_call_start("tu-1", "delegate", {"tasks": []})
        self.assertTrue(bb.blocks[0]["isInternal"])

    def test_server_list_matches_the_client_list(self):
        source = CLIENT_LIST.read_text()
        body = re.search(r"INTERNAL_TOOLS = new Set\(\[(.*?)\]\)", source, re.S)
        self.assertIsNotNone(body, f"INTERNAL_TOOLS not found in {CLIENT_LIST}")
        self.assertEqual(set(re.findall(r'"([^"]+)"', body.group(1))), set(INTERNAL_TOOLS))
