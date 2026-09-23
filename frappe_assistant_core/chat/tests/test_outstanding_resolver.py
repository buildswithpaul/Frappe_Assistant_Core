# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""One resolver answers "does this tenant owe money" for every surface.

The amount used to be reachable only through `get_payment_instrument`, called
when the Payment Method tab mounts — so the hero, the sidebar, the invoice list
and the Users page each had to either re-fetch it or invent their own signal.
The signal they could already see, `payment_status == "past_due"`, does not
agree with it: a stalled renewal freezes the cycle without necessarily marking
the subscription past due.
"""

import unittest
from unittest.mock import MagicMock

from frappe_assistant_core.chat.api.billing._outstanding import resolve_outstanding


def _client(payload):
    client = MagicMock()
    client.get_payment_instrument.return_value = payload
    return client


class TestResolveOutstanding(unittest.TestCase):
    def test_an_owed_invoice_is_reported(self):
        got = resolve_outstanding(
            _client({"amount_due": {"invoice": "INV-1", "amount": 7076.46, "currency": "INR"}})
        )
        self.assertEqual(got, {"amount": 7076.46, "currency": "INR", "invoice": "INV-1"})

    def test_nothing_owed_is_none_not_a_zero_amount(self):
        """Surfaces key on presence; a zero would light all four up over nothing."""
        self.assertIsNone(resolve_outstanding(_client({"amount_due": None})))
        self.assertIsNone(resolve_outstanding(_client({})))

    def test_a_zero_or_negative_balance_is_not_outstanding(self):
        self.assertIsNone(resolve_outstanding(_client({"amount_due": {"amount": 0}})))
        self.assertIsNone(resolve_outstanding(_client({"amount_due": {"amount": -50}})))

    def test_a_failing_ar_call_costs_the_notice_not_the_page(self):
        """Callers run this inside a fan-out that assembles a whole page."""
        client = MagicMock()
        client.get_payment_instrument.side_effect = RuntimeError("AR unreachable")
        self.assertIsNone(resolve_outstanding(client))

    def test_an_unparseable_amount_is_refused_rather_than_rendered(self):
        self.assertIsNone(resolve_outstanding(_client({"amount_due": {"amount": "lots"}})))

    def test_currency_is_passed_through_never_guessed(self):
        """Defaulting would relabel a foreign amount rather than admit we
        do not know what it is denominated in."""
        got = resolve_outstanding(_client({"amount_due": {"amount": 10, "currency": None}}))
        self.assertIsNone(got["currency"])


class TestBothPayloadsUseTheOneResolver(unittest.TestCase):
    """The drift this is built to prevent: a second surface growing its own
    private copy of "does the tenant owe money", which then disagrees."""

    def test_the_billing_page_and_the_boot_payload_share_it(self):
        import inspect

        from frappe_assistant_core.chat.api import init
        from frappe_assistant_core.chat.api.billing import combined

        self.assertIn("resolve_outstanding", inspect.getsource(combined))
        self.assertIn("resolve_outstanding", inspect.getsource(init))

    def test_the_boot_payload_never_omits_the_key(self):
        """The SPA must not have to tell "nothing owed" apart from "this
        payload predates the field", so EVERY return path carries the key —
        including the early exit for a user who cannot use FAC yet.

        Read from the AST rather than by counting substrings: the docstring
        names the field too, and a test that breaks when a comment is reworded
        teaches people to stop trusting it.
        """
        import ast
        import inspect
        import textwrap

        from frappe_assistant_core.chat.api import init

        tree = ast.parse(textwrap.dedent(inspect.getsource(init.initialize_spa)))
        returns = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
        ]
        self.assertGreaterEqual(len(returns), 2, "expected the early exit and the full payload")
        for node in returns:
            keys = [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
            self.assertIn("outstanding", keys, f"return at line {node.lineno} drops the key")
