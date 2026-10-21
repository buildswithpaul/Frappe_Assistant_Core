# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A turn sent with no model choice runs on the user's saved model; an explicit choice wins."""

import inspect
from concurrent.futures import Future
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api import models
from frappe_assistant_core.chat.api.chat import messages
from frappe_assistant_core.tests.base_test import BaseAssistantTest

GATE = "frappe_assistant_core.chat.api.settings.can_use_faco"
CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"
SAVED = "claude-opus-4-1"


def _sent_model(submit) -> str | None:
    """The model start_turn handed the relay, found by name so a reordered signature cannot hide it."""
    params = list(inspect.signature(messages._relay_ar_stream).parameters)
    return submit.call_args.args[1 + params.index("model_id")]


class TestTurnModelDefault(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # Production fills this cache whenever get_available_models runs (the SPA does at load).
        frappe.cache.delete_value(models.available_models_key())
        self.addCleanup(frappe.cache.delete_value, models.available_models_key())

    def _turn(self, saved, usable=(SAVED, "gpt-5"), **kwargs):
        # The saved value is what set_selected_model stores for the user; the AR list is what
        # list_available_models answers for their plan.
        ar = MagicMock()
        ar.list_available_models.return_value = {"models": [{"model_id": m} for m in usable]}
        with (
            patch(GATE, return_value={"can_use": True}),
            patch.object(models, "_saved_model", return_value=saved),
            patch(CLIENT, return_value=ar),
            patch.object(messages._relay_pool, "submit", return_value=Future()) as submit,
        ):
            messages.start_turn("s-model-default", "hi", **kwargs)
        return _sent_model(submit), ar

    def test_no_choice_uses_the_saved_model(self):
        for sent in ({}, {"model_id": None}, {"model_id": ""}, {"model_id": "  "}):
            with self.subTest(sent=sent):
                self.assertEqual(self._turn(SAVED, **sent)[0], SAVED)

    def test_explicit_auto_stays_auto(self):
        self.assertEqual(self._turn(SAVED, model_id="auto")[0], "auto")

    def test_saved_auto_is_used_without_asking_ar(self):
        model, ar = self._turn("auto")
        self.assertEqual(model, "auto")
        ar.list_available_models.assert_not_called()

    def test_explicit_model_wins_even_when_unavailable(self):
        self.assertEqual(self._turn(SAVED, usable=(), model_id="retired-model")[0], "retired-model")

    def test_nothing_saved_leaves_the_default_to_ar(self):
        self.assertIsNone(self._turn("", model_id=None)[0])

    def test_a_saved_model_the_user_can_no_longer_use_runs_on_the_default(self):
        self.assertIsNone(self._turn(SAVED, usable=("gpt-5",))[0])

    def test_an_unreachable_model_list_runs_on_the_default(self):
        ar = MagicMock()
        ar.list_available_models.side_effect = RuntimeError("AR down")
        with (
            patch(GATE, return_value={"can_use": True}),
            patch.object(models, "_saved_model", return_value=SAVED),
            patch(CLIENT, return_value=ar),
            patch.object(messages._relay_pool, "submit", return_value=Future()) as submit,
        ):
            messages.start_turn("s-model-default", "hi")
        self.assertIsNone(_sent_model(submit))

    def test_the_model_list_is_asked_once_then_cached(self):
        _, ar = self._turn(SAVED)
        self._turn(SAVED)
        self.assertEqual(ar.list_available_models.call_count, 1)

    def test_an_ar_outage_is_remembered_briefly_so_turns_do_not_each_wait(self):
        ar = MagicMock()
        ar.list_available_models.side_effect = RuntimeError("AR down")
        with (
            patch(GATE, return_value={"can_use": True}),
            patch.object(models, "_saved_model", return_value=SAVED),
            patch(CLIENT, return_value=ar),
            patch.object(messages._relay_pool, "submit", return_value=Future()) as submit,
        ):
            messages.start_turn("s-model-default", "hi")
            messages.start_turn("s-model-default", "hi again")
        self.assertEqual(ar.list_available_models.call_count, 1)
        self.assertIsNone(_sent_model(submit))
