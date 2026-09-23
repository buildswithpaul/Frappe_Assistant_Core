import unittest
from unittest.mock import patch

from frappe_assistant_core.chat.api._helpers import (
    _redact_upstream_internals,
    _summarize_stream_error_for_log,
)
from frappe_assistant_core.chat.api.chat.helpers import _log_stream_error_detail


class TestRedactUpstreamInternals(unittest.TestCase):
    def test_strips_saas_table_name(self):
        raw = (
            '(1020, "Record has changed since last read in table '
            "'tabAR Tenant User'; try restarting transaction\")"
        )
        out = _redact_upstream_internals(raw)
        self.assertNotIn("tabAR", out)
        self.assertNotIn("AR Tenant User", out)
        self.assertIn("Record has changed since last read", out)

    def test_strips_backticked_table(self):
        out = _redact_upstream_internals("UPDATE `tabAR Tenant User` SET x=1")
        self.assertNotIn("tabAR", out)
        self.assertIn("[internal table]", out)

    def test_strips_module_path(self):
        out = _redact_upstream_internals("assistant_runtime.agent.agent_pool.AgentPool failed")
        self.assertNotIn("assistant_runtime", out)

    def test_renames_legacy_stream_error_title(self):
        out = _redact_upstream_internals("AR stream_error: LLM_UNAVAILABLE")
        self.assertNotIn("AR stream_error", out)
        self.assertIn("FAC Chat stream error", out)


class TestLogStreamErrorDetail(unittest.TestCase):
    def test_drops_detail_and_never_logs_table_names(self):
        data = {
            "error": "The AI is temporarily unavailable.",
            "error_code": "LLM_UNAVAILABLE",
            "_detail": (
                '(1020, "Record has changed since last read in table '
                "'tabAR Tenant User'; try restarting transaction\")"
            ),
        }
        logged = {}

        def fake_log(*, title, detail):
            logged["title"] = title
            logged["detail"] = detail

        with patch("frappe_assistant_core.chat.api._helpers._log", side_effect=fake_log):
            _log_stream_error_detail(data)

        self.assertNotIn("_detail", data)
        self.assertEqual(logged["title"], "FAC Chat stream error: LLM_UNAVAILABLE")
        self.assertNotIn("tabAR", logged["detail"])
        self.assertNotIn("AR stream_error", logged["title"])
        self.assertIn("LLM_UNAVAILABLE", logged["detail"])

    def test_summary_never_embeds_raw_exception(self):
        body = _summarize_stream_error_for_log("LLM_UNAVAILABLE")
        self.assertIn("LLM_UNAVAILABLE", body)
        self.assertNotIn("tabAR", body)
        self.assertNotIn("1020", body)

    def test_skips_log_when_no_upstream_detail(self):
        logged = []
        with patch(
            "frappe_assistant_core.chat.api._helpers._log",
            side_effect=lambda **kw: logged.append(kw),
        ):
            _log_stream_error_detail({"error_code": "LLM_UNAVAILABLE"})
        self.assertEqual(logged, [])
