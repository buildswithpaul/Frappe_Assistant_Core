# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Importing from a Google Sheets link (#34006).

FAC downloads the tab's CSV export, bounded in size and time, and keeps a private copy of it,
so the session works on a file on the site like any other and what the dry run checked is what
gets imported. Google is never reached here: ``requests.get`` returns real Response objects
built the way Google answers, so the checks of the reply run as they do live.
"""

import unittest
from unittest.mock import patch

import frappe
import requests

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_session

LINK = "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMn/edit#gid=0"
EXPORT = "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMn/export?format=csv&gid=0"
CSV_CONTENT = b"Customer Name,Customer Group,Territory\n" + b"".join(
    f"Customer {i},Retail,India\n".encode() for i in range(1, 26)
)
# What Google sends for a sheet that isn't shared: its sign-in page, with 200 OK.
SIGN_IN_PAGE = b"<!doctype html><html><head><title>Sign in</title></head><body></body></html>"
SHARE_ADVICE = "Anyone with the link"


def _reply(status: int, content: bytes, content_type: str = "text/csv") -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = content
    response._content_consumed = True  # read as it streams in, the body comes in pieces
    response.encoding = "utf-8"
    response.headers["Content-Type"] = content_type
    response.url = EXPORT
    return response


def _google(*replies):
    """Patch the sheet's download: each call gets the next reply (or raises it)."""
    return patch("requests.get", autospec=True, side_effect=list(replies))


def _endless(reply, chunk=b"Customer,Retail,India\n" * 50):
    """Make ``reply`` a body that never ends, as a huge or trickling sheet would. Returns the
    list of chunks read, to show where reading stopped."""
    read = []

    def chunks(chunk_size=1, decode_unicode=False):
        while True:
            read.append(chunk)
            yield chunk

    reply.iter_content = chunks
    return read


class TestStartFromGoogleSheet(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()
        # A plain desk user: owns the files they upload, holds no import rights.
        self.user = self.make_desk_user("sheets")
        self.assert_cannot(self.user, "create", "Data Import")
        frappe.set_user(self.user)
        self.track_test_files()
        self.sessions_before = frappe.db.count("FAC Import Session")

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    def _run(self, arguments):
        return self.registry.get_tool("start_import_session")._safe_execute(arguments)

    def _start_fails(self, expected_text, **arguments):
        response = self._run(arguments)
        self.assertFalse(response["success"], response)
        self.assertIn(expected_text, response["error"])
        return response

    def _new_sessions(self):
        return frappe.db.count("FAC Import Session") - self.sessions_before

    # -- criterion 1: a shared link opens a session, the same as an uploaded file ----------

    def test_a_shared_sheet_opens_a_session_on_a_private_copy_of_it(self):
        with _google(_reply(200, CSV_CONTENT)) as get:
            response = self._run({"google_sheets_url": LINK})

        self.assertTrue(response["success"], response)
        result = response["result"]
        self.assertEqual(get.call_args.args[0], EXPORT)
        self.assertEqual(result["columns"], ["Customer Name", "Customer Group", "Territory"])
        self.assertEqual(result["row_count"], 25)
        self.assertEqual(result["sample_rows"][0], ["Customer 1", "Retail", "India"])
        session = frappe.get_doc("FAC Import Session", result["session_id"])
        self.assertEqual((session.file_source, session.source_url), ("Google Sheet", LINK))
        copy = frappe.get_doc("File", session.source_file)
        self.assertEqual((copy.is_private, copy.owner), (1, self.user))
        self.assertEqual(frappe.safe_encode(copy.get_content()), CSV_CONTENT)

    def test_the_reply_says_only_one_tab_is_read(self):
        with _google(_reply(200, CSV_CONTENT)):
            response = self._run({"google_sheets_url": LINK})

        self.assertTrue(response["success"], response)
        self.assertIn("copy the link again", response["result"]["note"])

    # -- criterion 2: a sheet that can't be read is explained, never a silent failure ------

    def test_a_sheet_that_cant_be_read_explains_how_to_share_it(self):
        frappe.clear_messages()  # setUp's user creation leaves its own messages
        replies = {
            "not shared: Google's sign-in page": _reply(200, SIGN_IN_PAGE, "text/html"),
            "deleted or mistyped": _reply(404, SIGN_IN_PAGE, "text/html"),
            "no access": _reply(403, SIGN_IN_PAGE, "text/html"),
            "a tab that isn't there": _reply(400, SIGN_IN_PAGE, "text/html"),
        }
        for case, reply in replies.items():
            with self.subTest(case), _google(reply):
                response = self._start_fails(SHARE_ADVICE, google_sheets_url=LINK)
                self.assertNotIn("Client Error", response["error"])

            self.assertEqual((self._new_sessions(), self.new_files()), (0, set()))
        # Frappe's own "not publicly accessible" pop-up is not left for the page to show.
        self.assertFalse(frappe.local.message_log)

    def test_google_not_answering_asks_to_try_again(self):
        for case, reply in {
            "no connection": requests.ConnectionError("down"),
            "no answer in time": requests.Timeout("slow"),
            "Google's own error": _reply(503, b"", "text/html"),
        }.items():
            with self.subTest(case), _google(reply):
                self._start_fails("try again", google_sheets_url=LINK)

            self.assertEqual((self._new_sessions(), self.new_files()), (0, set()))

    # -- the download is bounded: a huge or slow sheet can't hold the server up -----------

    def test_the_sheet_is_streamed_with_a_time_limit(self):
        with _google(_reply(200, CSV_CONTENT)) as get:
            self.assertTrue(self._run({"google_sheets_url": LINK})["success"])

        self.assertIs(get.call_args.kwargs.get("stream"), True)
        self.assertTrue(get.call_args.kwargs.get("timeout"))

    def test_a_sheet_that_says_it_is_too_large_is_not_read(self):
        reply = _reply(200, b"")
        reply.headers["Content-Length"] = str(import_session.MAX_FILE_SIZE + 1)
        read = _endless(reply)
        with _google(reply):
            self._start_fails("larger than", google_sheets_url=LINK)

        self.assertEqual(read, [])
        self.assertEqual((self._new_sessions(), self.new_files()), (0, set()))

    def test_reading_stops_once_the_sheet_passes_the_size_limit(self):
        reply = _reply(200, b"")
        read = _endless(reply)
        with patch.object(import_session, "MAX_FILE_SIZE", 10_000), _google(reply):
            self._start_fails("larger than", google_sheets_url=LINK)

        self.assertLess(sum(len(chunk) for chunk in read), 10_000 + len(read[0]) + 1)
        self.assertEqual((self._new_sessions(), self.new_files()), (0, set()))

    def test_reading_stops_at_the_sites_own_file_size_limit(self):
        # Frappe's File refuses anything over System Settings' Max File Size (25 MB by default):
        # past it, the sheet is refused while it is read, with the size the site takes.
        reply = _reply(200, b"")
        read = _endless(reply)
        with patch.object(import_session, "get_max_file_size", return_value=10_000), _google(reply):
            error = self._start_fails("larger than", google_sheets_url=LINK)

        self.assertLess(sum(len(chunk) for chunk in read), 10_000 + len(read[0]) + 1)
        self.assertNotIn("50 MB", str(error))

    def test_the_sheet_is_read_as_it_arrives(self):
        # Pieces as the network gives them: a 64 KB piece trickling in would hold the read
        # (and put off the time limit) until the whole piece came.
        reply = _reply(200, CSV_CONTENT)
        asked = []
        real = reply.iter_content
        reply.iter_content = lambda chunk_size=1, decode_unicode=False: asked.append(chunk_size) or real(1024)
        with _google(reply):
            self.assertTrue(self._run({"google_sheets_url": LINK})["success"])

        self.assertEqual(asked, [None])

    def test_only_the_tab_of_a_range_link_is_read(self):
        # "Get link to this range" adds &range=… after the gid: the whole tab is read, not the range
        with _google(_reply(200, CSV_CONTENT)) as get:
            self.assertTrue(self._run({"google_sheets_url": LINK + "&range=A1:C3"})["success"])

        self.assertEqual(get.call_args.args[0], EXPORT)

    def test_a_sheet_that_takes_too_long_is_given_up(self):
        reply = _reply(200, b"")
        read = _endless(reply)
        # A deadline already past: the first piece read finds the time is up.
        with patch.object(import_session, "DOWNLOAD_SECONDS", -1), _google(reply):
            self._start_fails("try again", google_sheets_url=LINK)

        self.assertEqual(len(read), 1)
        self.assertEqual((self._new_sessions(), self.new_files()), (0, set()))

    def test_a_link_that_isnt_a_google_sheet_is_refused_without_downloading(self):
        for link in (
            "https://example.com/spreadsheets/customers.csv",
            "http://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMn/edit",
            "https://drive.google.com/file/d/1AbCdEfGhIjKlMn/view",
        ):
            with self.subTest(link), _google() as get:
                self._start_fails("isn't a Google Sheets link", google_sheets_url=link)

            get.assert_not_called()
        self.assertEqual(self._new_sessions(), 0)

    def test_the_target_is_checked_before_the_sheet_is_downloaded(self):
        with _google() as get:
            self._start_fails(
                "permission to create Currency", google_sheets_url=LINK, target_doctype="Currency"
            )

        get.assert_not_called()

    def test_a_link_with_a_file_is_refused(self):
        with _google() as get:
            self._start_fails("only", google_sheets_url=LINK, file_id="8f3a2b1c9d")
            self._start_fails("only", google_sheets_url=LINK, file_url="/private/files/customers.csv")

        get.assert_not_called()

    def test_a_sheet_over_the_row_limit_leaves_no_copy_behind(self):
        # An administrator lowers Max Rows per Import in Assistant Core Settings.
        before = frappe.db.get_single_value("Assistant Core Settings", "max_import_rows")
        self.addCleanup(frappe.db.set_single_value, "Assistant Core Settings", "max_import_rows", before)
        frappe.db.set_single_value("Assistant Core Settings", "max_import_rows", 10)

        with _google(_reply(200, CSV_CONTENT)):
            self._start_fails("more than the 10", google_sheets_url=LINK)

        self.assertEqual((self._new_sessions(), self.new_files()), (0, set()))

    def test_a_session_that_cant_be_saved_leaves_no_copy_behind(self):
        from frappe_assistant_core.plugins.migration.tools.start_import_session import StartImportSession

        with (
            _google(_reply(200, CSV_CONTENT)),
            patch.object(
                StartImportSession,
                "_create_session",
                autospec=True,
                side_effect=frappe.ValidationError("the session couldn't be saved"),
            ),
        ):
            response = self._run({"google_sheets_url": LINK})

        self.assertFalse(response["success"], response)
        self.assertEqual((self._new_sessions(), self.new_files()), (0, set()))


GROUP = "FAC Sheets Group"
MAPPING = {"Customer Name": "customer_name", "Customer Group": "customer_group"}


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestCheckGoogleSheetAgain(BaseAssistantTest):
    """The user fixes the sheet in Google Sheets and asks for it to be checked again."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.registry = get_tool_registry()
        self.track_test_files()
        self.tag = frappe.generate_hash(length=6)
        if not frappe.db.exists("Customer Group", GROUP):
            frappe.get_doc(
                {
                    "doctype": "Customer Group",
                    "customer_group_name": GROUP,
                    "parent_customer_group": "All Customer Groups",
                    "is_group": 0,
                }
            ).insert()

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _csv(self, group, header=b"Customer Name,Customer Group\n"):
        return header + f"Sheet {self.tag},{group}\n".encode()

    def _session(self, content):
        """A session opened from the link and mapped, as the earlier steps do."""
        with _google(_reply(200, content)):
            started = self._run("start_import_session", {"google_sheets_url": LINK})
        self.assertTrue(started["success"], started)
        session = started["result"]["session_id"]
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": MAPPING, "doctype": "Customer"}
        )
        self.assertTrue(mapped["success"], mapped)
        return session

    @staticmethod
    def _copies():
        """The copies of a Google Sheet on the site (a check also saves its results as a File)."""
        return set(frappe.get_all("File", filters={"file_name": ["like", "google-sheet-%"]}, pluck="name"))

    def _check(self, session, content=None):
        arguments = {"session": session}
        if content is None:
            return self._run("dry_run_import", arguments)
        with _google(_reply(200, content)):
            return self._run("dry_run_import", {**arguments, "google_sheets_url": LINK})

    def test_a_fixed_sheet_is_checked_again_from_its_link(self):
        session = self._session(self._csv(f"Retial {self.tag}"))
        first = self._check(session)
        self.assertEqual(first["result"]["failed"], 1, first)
        first_copy = frappe.db.get_value("FAC Import Session", session, "source_file")

        again = self._check(session, self._csv(GROUP))

        self.assertTrue(again["success"], again)
        self.assertEqual((again["result"]["ready"], again["result"]["failed"]), (1, 0))
        doc = frappe.get_doc("FAC Import Session", session)
        self.assertNotEqual(doc.source_file, first_copy)
        self.assertEqual((doc.file_source, doc.source_url), ("Google Sheet", LINK))
        self.assertEqual(
            frappe.parse_json(doc.template_options)["column_to_field_map"],
            {"0": "customer_name", "1": "customer_group"},
        )

    def test_a_sheet_whose_columns_changed_keeps_the_session_as_it_was(self):
        session = self._session(self._csv(GROUP))
        copy = frappe.db.get_value("FAC Import Session", session, "source_file")
        copies = self._copies()

        response = self._check(session, self._csv(GROUP, header=b"Name,Group,Phone\n"))

        self.assertFalse(response["success"], response)
        self.assertIn("columns don't match", response["error"])
        self.assertEqual(frappe.db.get_value("FAC Import Session", session, "source_file"), copy)
        self.assertEqual(self._copies(), copies)

    def test_an_unchanged_sheet_leaves_no_second_copy(self):
        session = self._session(self._csv(GROUP))
        copy = frappe.db.get_value("FAC Import Session", session, "source_file")
        copies = self._copies()

        response = self._check(session, self._csv(GROUP))

        self.assertTrue(response["success"], response)
        self.assertEqual(frappe.db.get_value("FAC Import Session", session, "source_file"), copy)
        self.assertEqual(self._copies(), copies)
        self.assertTrue(frappe.db.exists("File", copy))
