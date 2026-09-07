import json
import unittest

from frappe_assistant_core.chat.api.block_builder import (
    MAX_EMIT_RESULT_CHARS,
    truncate_result_for_emit,
)


class TestTruncateResultForEmit(unittest.TestCase):
    def test_short_string_passes_through(self):
        self.assertEqual(truncate_result_for_emit("hello"), "hello")

    def test_long_string_is_truncated(self):
        big = "x" * (MAX_EMIT_RESULT_CHARS + 500)
        out = truncate_result_for_emit(big)
        self.assertTrue(len(out) < len(big))
        self.assertTrue(out.startswith("x" * 100))
        self.assertIn("truncated", out)

    def test_dict_preserves_structural_keys(self):
        result = {
            "success": True,
            "file_url": "/files/report.pdf",
            "file_name": "report.pdf",
            "data": "y" * (MAX_EMIT_RESULT_CHARS + 500),
        }
        out = truncate_result_for_emit(result)
        # structural keys preserved verbatim
        self.assertIs(out["success"], True)
        self.assertEqual(out["file_url"], "/files/report.pdf")
        self.assertEqual(out["file_name"], "report.pdf")
        # large free-text value truncated
        self.assertTrue(len(out["data"]) < MAX_EMIT_RESULT_CHARS + 500)
        self.assertIn("truncated", out["data"])

    def test_dict_short_values_untouched(self):
        result = {"success": False, "message": "no rows found"}
        self.assertEqual(truncate_result_for_emit(result), result)

    def test_does_not_mutate_input(self):
        big = "z" * (MAX_EMIT_RESULT_CHARS + 500)
        result = {"data": big}
        _ = truncate_result_for_emit(result)
        self.assertEqual(result["data"], big)  # original unchanged

    def test_large_list_becomes_preview(self):
        result = [{"row": i, "pad": "q" * 200} for i in range(1000)]
        out = truncate_result_for_emit(result)
        self.assertIsInstance(out, dict)
        self.assertTrue(out["_truncated"])
        self.assertIn("preview", out)
        self.assertTrue(len(json.dumps(out)) < len(json.dumps(result)))

    def test_scalar_passthrough(self):
        self.assertEqual(truncate_result_for_emit(42), 42)
        self.assertIsNone(truncate_result_for_emit(None))
        self.assertIs(truncate_result_for_emit(True), True)
