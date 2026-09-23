"""The trigger payload must round-trip through strict json.dumps (no default=).

build_payload's own size-check uses ``json.dumps(..., default=str)`` which
masks non-native leaves — the payload then explodes later in the SDK's strict
serialization. The shipped bug: MariaDB returns Time/Duration columns as
``timedelta`` (e.g. Sales Invoice.posting_time), which _coerce_json_native
did not handle, so every doc_event fire on such doctypes failed with
"Object of type timedelta is not JSON serializable".
"""

import datetime
import json
import unittest
import uuid
from decimal import Decimal

from frappe_assistant_core.chat.workflows.triggers.filters import _coerce_json_native

_SAMPLES = {
    "uuid": uuid.uuid4(),
    "decimal": Decimal("99.90"),
    "datetime": datetime.datetime(2026, 7, 21, 16, 50, 29),
    "date": datetime.date(2026, 7, 21),
    "time": datetime.time(16, 50, 29),
    "timedelta": datetime.timedelta(hours=16, minutes=50, seconds=29),
    "bytes": b"abc",
    "str": "plain",
    "int": 7,
    "float": 1.5,
    "none": None,
}


class TestCoerceJsonNative(unittest.TestCase):
    def test_timedelta_coerces_to_string(self):
        self.assertEqual(
            _coerce_json_native(datetime.timedelta(hours=16, minutes=50, seconds=29)),
            "16:50:29",
        )

    def test_every_coerced_leaf_survives_strict_json_dumps(self):
        coerced = {k: _coerce_json_native(v) for k, v in _SAMPLES.items()}
        json.dumps(coerced)  # must not raise — no default= on the SDK side


if __name__ == "__main__":
    unittest.main()
