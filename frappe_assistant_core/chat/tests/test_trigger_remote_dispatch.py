# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""AR failure classification and docname binding on the remote fire.

Classification used to string-match ``str(exc)``, which put a 403 plan gate and
a 401 auth failure in the retryable bucket where no retry could ever clear
them. Binding used to send the workflow's MUTABLE display name, so renaming an
agent in the builder silently killed every trigger pointed at it.
"""

import unittest

from assistant_runtime_sdk import (
    ARAPIError,
    ARAuthenticationError,
    ARConnectionError,
    ARRateLimitError,
    ARTimeoutError,
)

from frappe_assistant_core.chat.workflows.triggers import remote
from frappe_assistant_core.chat.workflows.triggers.log import (
    STATUS_AR_ERROR,
    STATUS_ENQUEUE_FAILED,
    STATUS_QUOTA_SKIPPED,
)


class TestClassifyException(unittest.TestCase):
    def _status(self, exc):
        return remote._classify_exception(exc)[0]

    def test_plan_gate_is_permanent(self):
        self.assertEqual(self._status(ARAPIError("Forbidden", status_code=403)), STATUS_AR_ERROR)

    def test_auth_failure_is_permanent(self):
        self.assertEqual(self._status(ARAuthenticationError("bad signature")), STATUS_AR_ERROR)

    def test_missing_workflow_is_permanent(self):
        self.assertEqual(self._status(ARAPIError("Not found", status_code=404)), STATUS_AR_ERROR)

    def test_quota_and_rate_limit_are_skipped(self):
        self.assertEqual(self._status(ARAPIError("Payment required", status_code=402)), STATUS_QUOTA_SKIPPED)
        self.assertEqual(self._status(ARAPIError("Too many", status_code=429)), STATUS_QUOTA_SKIPPED)
        self.assertEqual(self._status(ARRateLimitError()), STATUS_QUOTA_SKIPPED)

    def test_server_and_network_errors_are_retryable(self):
        self.assertEqual(self._status(ARAPIError("Bad gateway", status_code=502)), STATUS_ENQUEUE_FAILED)
        self.assertEqual(self._status(ARTimeoutError()), STATUS_ENQUEUE_FAILED)
        self.assertEqual(self._status(ARConnectionError()), STATUS_ENQUEUE_FAILED)

    def test_a_403_body_mentioning_404_is_still_permanent(self):
        """The old substring match keyed on digits anywhere in the message."""
        exc = ARAPIError("upstream returned 404 for /health", status_code=403)
        self.assertEqual(self._status(exc), STATUS_AR_ERROR)


class _SDKClient:
    """Stand-in for an SDK that already forwards workflow_docname."""

    workflows_api_base = "assistant_runtime_workflows.api"

    def __init__(self):
        self.calls = []

    def execute_workflow_from_event(
        self, workflow_name, input_data, user_id, trigger_id, workflow_docname=None
    ):
        self.calls.append(
            {
                "workflow_name": workflow_name,
                "workflow_docname": workflow_docname,
                "user_id": user_id,
                "trigger_id": trigger_id,
            }
        )
        return {"run_name": "WFR-00001"}


class _LegacySDKClient:
    """Stand-in for an installed SDK that predates the argument."""

    workflows_api_base = "assistant_runtime_workflows.api"

    def __init__(self):
        self.posted = []

    def execute_workflow_from_event(self, workflow_name, input_data, user_id, trigger_id):
        raise AssertionError("must not be called when a docname is available")

    def _prepare_execute_workflow_from_event(self, workflow_name, input_data, user_id, trigger_id):
        return "workflows.execute_from_event", {
            "workflow_name": workflow_name,
            "input_data": input_data,
            "user_id": user_id,
            "trigger_id": trigger_id,
        }

    def _request_post_json(self, endpoint, payload, api_base=None):
        self.posted.append((endpoint, payload))
        return {"run_name": "WFR-00002"}


class TestDocnameBinding(unittest.TestCase):
    def _fire(self, client, workflow_docname):
        return remote._execute_from_event(
            client,
            workflow_name="Invoice Summarizer",
            workflow_docname=workflow_docname,
            payload={"doc": {}},
            user_id="owner@example.com",
            trigger_id="TRG-1",
        )

    def test_docname_is_forwarded_when_the_sdk_accepts_it(self):
        client = _SDKClient()
        self._fire(client, "WF-00007")
        self.assertEqual(client.calls[0]["workflow_docname"], "WF-00007")

    def test_display_name_only_when_no_docname_is_bound(self):
        client = _SDKClient()
        self._fire(client, "")
        self.assertIsNone(client.calls[0]["workflow_docname"])
        self.assertEqual(client.calls[0]["workflow_name"], "Invoice Summarizer")

    def test_an_older_sdk_still_carries_the_docname(self):
        client = _LegacySDKClient()
        result = self._fire(client, "WF-00007")
        _endpoint, payload = client.posted[0]
        self.assertEqual(payload["workflow_docname"], "WF-00007")
        self.assertEqual(result["run_name"], "WFR-00002")
