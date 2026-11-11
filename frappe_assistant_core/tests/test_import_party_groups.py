"""
A preset's Customers and Suppliers (a Tally ledgers export) bring no group or territory column, so
each record takes the Selling or Buying Settings default. Live 2026-11-10 (FAC Chat, v16): with no
default the Tally customers were saved with no Customer Group or Territory and the check said
nothing; with a group-node default (v15 fac-b) every row was refused. The check now reports the
field as a required value missing, which the user fills with one leaf. A site with a default that
can hold records, and a file the user maps themselves, are checked exactly as before.
"""

import frappe

from frappe_assistant_core.tests.test_apply_import_preset_xml import TallyXmlToolCase
from frappe_assistant_core.tests.test_import_tally_xml import group, ledger

LEDGERS = (
    group("Sundry Debtors"),
    group("Sundry Creditors"),
    ledger("Kaveri Eng {tag}", "Sundry Debtors"),
    ledger("Polycab {tag}", "Sundry Creditors"),
)
SETTINGS = {
    "customer_group": ("Selling Settings", "Customer Group"),
    "territory": ("Selling Settings", "Territory"),
    "supplier_group": ("Buying Settings", "Supplier Group"),
}
MISSING = "Required value missing"


class TestPartyGroups(TallyXmlToolCase):
    def setUp(self):
        super().setUp()
        self.before = {
            f: (frappe.db.get_single_value(s, f), frappe.db.get_default(f)) for f, (s, _l) in SETTINGS.items()
        }
        self.leaf = {f: frappe.db.get_value(link, {"is_group": 0}) for f, (_s, link) in SETTINGS.items()}
        self.node = {f: frappe.db.get_value(link, {"is_group": 1}) for f, (_s, link) in SETTINGS.items()}
        # Every default holds records unless a test says otherwise
        for field in SETTINGS:
            self._default(field, self.leaf[field])

    def tearDown(self):
        for field, (setting, default) in self.before.items():
            frappe.db.set_single_value(SETTINGS[field][0], field, setting or "")
            frappe.db.set_default(field, default or "")
        super().tearDown()

    def _default(self, field, value):
        # What a new record gets is the site default (Selling/Buying Settings write it on save)
        frappe.db.set_single_value(SETTINGS[field][0], field, value or "")
        frappe.db.set_default(field, value or "")

    def _tool(self, name, arguments):
        reply = self.registry.get_tool(name)._safe_execute(arguments)
        return reply.get("result") if isinstance(reply.get("result"), dict) else reply

    def _sessions(self):
        result = self._ok({"file_id": self._file(*LEDGERS).name, "parts": ["ledgers"]})
        return {s["target"]: s["session_id"] for s in result["results"][0]["sessions"]}

    def _check(self, session, fixes=None):
        return self._tool("dry_run_import", {"session": session, **({"fixes": fixes} if fixes else {})})

    @staticmethod
    def _gap(result, field):
        return next(
            (g for g in result.get("groups") or [] if g.get("cause") == MISSING and g.get("field") == field),
            None,
        )

    # -- the site's default can hold records: as before -------------------------------------

    def test_a_default_that_holds_records_is_used_as_before(self):
        result = self._check(self._sessions()["Customers"])
        self.assertIsNone(self._gap(result, "customer_group"), result.get("groups"))
        self.assertIsNone(self._gap(result, "territory"), result.get("groups"))
        self.assertEqual(result.get("ready"), 1, result)

    def test_a_group_node_territory_or_supplier_group_is_accepted_as_before(self):
        # ERPNext saves a party under a group-node Territory or Supplier Group: not reported
        self._default("territory", self.node["territory"])
        self._default("supplier_group", self.node["supplier_group"])
        sessions = self._sessions()
        customers, suppliers = self._check(sessions["Customers"]), self._check(sessions["Suppliers"])
        self.assertIsNone(self._gap(customers, "territory"), customers.get("groups"))
        self.assertIsNone(self._gap(suppliers, "supplier_group"), suppliers.get("groups"))

    # -- no default, or a group node: the check says so, and offers one value ------------------

    def test_no_default_customer_group_is_a_required_value_missing_with_a_fill(self):
        self._default("customer_group", None)
        result = self._check(self._sessions()["Customers"])
        gap = self._gap(result, "customer_group")
        self.assertIsNotNone(gap, result.get("groups"))
        self.assertEqual(result.get("ready"), 0, result)
        self.assertIn("fill", [f["action"] for f in gap["fixes"]])
        self.assertIn("leave_out", [f["action"] for f in gap["fixes"]])
        self.assertIsNone(self._gap(result, "territory"))  # its default still holds records

    def test_a_group_node_default_is_reported_the_same_way_not_refused_by_erpnext(self):
        self._default("customer_group", self.node["customer_group"])
        result = self._check(self._sessions()["Customers"])
        self.assertIsNotNone(self._gap(result, "customer_group"), result.get("groups"))
        self.assertFalse(
            [g for g in result.get("groups") or [] if g.get("cause") == "Rejected by ERPNext"],
            result.get("groups"),
        )

    def test_no_default_territory_is_reported_too(self):
        self._default("territory", None)
        result = self._check(self._sessions()["Customers"])
        self.assertIsNotNone(self._gap(result, "territory"), result.get("groups"))

    def test_no_default_supplier_group_is_reported_for_suppliers(self):
        self._default("supplier_group", None)
        result = self._check(self._sessions()["Suppliers"])
        self.assertIsNotNone(self._gap(result, "supplier_group"), result.get("groups"))

    def test_filling_a_group_that_holds_records_makes_the_rows_ready(self):
        self._default("customer_group", None)
        session = self._sessions()["Customers"]
        gap = self._gap(self._check(session), "customer_group")
        result = self._check(
            session, [{"group": gap["id"], "action": "fill", "value": self.leaf["customer_group"]}]
        )
        if result.get("state") != "running":
            result = self._check(session)
        self.assertIsNone(self._gap(result, "customer_group"), result.get("groups"))
        self.assertEqual(result.get("ready"), 1, result)

    def test_filling_a_group_node_is_refused_with_groups_that_can_hold_records(self):
        self._default("customer_group", None)
        session = self._sessions()["Customers"]
        gap = self._gap(self._check(session), "customer_group")
        reply = self.registry.get_tool("dry_run_import")._safe_execute(
            {
                "session": session,
                "fixes": [{"group": gap["id"], "action": "fill", "value": self.node["customer_group"]}],
            }
        )
        text = frappe.as_json(reply)
        self.assertIn("is a group, so it can't hold records", text)
        self.assertIn(self.leaf["customer_group"], text)

    # -- a file the user maps themselves: unchanged --------------------------------------------

    def test_a_plain_customers_file_is_checked_as_before(self):
        self._default("customer_group", None)
        file_doc = self._upload(
            f"Customer Name,Customer Type\nPlain {self.tag},Company\n".encode(),
            file_name=f"plain-{self.tag}.csv",
        )
        session = self._tool("start_import_session", {"file_url": file_doc.file_url})["session_id"]
        self._tool(
            "set_column_mapping",
            {
                "session": session,
                "doctype": "Customer",
                "mapping": {"Customer Name": "customer_name", "Customer Type": "customer_type"},
            },
        )
        result = self._check(session)
        self.assertIsNone(self._gap(result, "customer_group"), result.get("groups"))
