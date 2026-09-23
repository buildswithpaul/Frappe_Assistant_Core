# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import frappe
from frappe import _
from frappe.model.document import Document

#: System DocTypes that generate background noise on every bench action.
#: Targeting these would fire the user's workflow on every doc save site-wide.
SYSTEM_NOISE_DOCTYPES = frozenset(
    {
        "Version",
        "Activity Log",
        "Document Follow",
        "Error Log",
        "File",
        "Communication",
        "Comment",
        "Note",
        "DocType",
        "Custom Field",
        "Property Setter",
        "Scheduled Job Log",
    }
)


#: DocTypes the trigger pipeline itself writes — targeting them would loop.
INTERNAL_LOOP_DOCTYPES = frozenset(
    {
        "FAC Workflow Trigger",
        "FAC Workflow Trigger Filter",
        "FAC Workflow Trigger Log",
    }
)

#: FAC chat DocTypes that the chat pipeline writes on every user turn.
#: Allowing triggers on these would fire a workflow on every chat message —
#: almost always unintended. Users who genuinely want this can grant
#: exceptions in future versions; default is to hide them.
FAC_INTERNAL_DOCTYPES = frozenset(
    {
        "FAC Chat Usage Log",
        "FAC Chat Message",
    }
)

#: Anything a user cannot pick as a trigger target. The UI hides these; the
#: controller rejects them; the dispatcher skips them on the hot path.
DOCTYPE_BLOCKLIST = SYSTEM_NOISE_DOCTYPES | INTERNAL_LOOP_DOCTYPES | FAC_INTERNAL_DOCTYPES

VALID_EVENTS = {
    "after_insert",
    "on_update",
    "on_submit",
    "on_cancel",
    "on_trash",
}


def _invalidate_trigger_map() -> None:
    """Invalidate the cached trigger map after a trigger is saved or deleted.

    Delegates to frappe_assistant_core.chat.workflows.triggers.map when that
    module is present (migrated in the workflow dispatcher task). Silently
    skips if the module does not exist yet.

    NOTE (Task 3.6 forward-ref): The trigger-map cache module lives at
    frappe_assistant_core.chat.workflows.triggers.map and must be migrated
    as part of the workflow dispatcher migration (Task 3.9).
    """
    try:
        from frappe_assistant_core.chat.workflows.triggers.map import (
            invalidate as _invalidate,
        )

        _invalidate()
    except ImportError:
        pass


class FACWorkflowTrigger(Document):
    """Binds a customer DocType event to a remote FAC Cloud workflow."""

    def before_insert(self):
        if not self.tenant:
            try:
                # NOTE (Task 3.6 forward-ref): Settings DocType was renamed from
                # "FACO Settings" to "FAC Chat Settings" in Task 3.2. Using the
                # FAC-canonical name here; FACO installs will still resolve via
                # their own Settings DocType.
                settings = frappe.get_single("FAC Chat Settings")
                tenant_id = getattr(settings, "tenant_id", None) or getattr(settings, "ar_tenant_id", None)
                if tenant_id:
                    self.tenant = tenant_id
            except Exception:
                pass

        if not self.created_by_user:
            self.created_by_user = frappe.session.user

    def validate(self):
        # DocType: exists, non-blocklisted, non-system-namespace, non-table, non-single
        if not self.reference_doctype:
            frappe.throw(_("Reference DocType is required."))

        name = self.reference_doctype.strip()
        self.reference_doctype = name  # normalise whitespace

        if name in INTERNAL_LOOP_DOCTYPES:
            frappe.throw(
                _(
                    "DocType '{0}' is used by the trigger pipeline itself. Targeting it would create an infinite loop."
                ).format(name)
            )
        if name in SYSTEM_NOISE_DOCTYPES:
            frappe.throw(
                _(
                    "DocType '{0}' is a high-frequency system DocType and cannot be used as a trigger target."
                ).format(name)
            )

        if not frappe.db.exists("DocType", name):
            frappe.throw(
                _("Unknown DocType: '{0}'. Pick one from the dropdown.").format(name),
                frappe.DoesNotExistError,
            )

        meta = frappe.get_meta(name)
        if meta.istable:
            frappe.throw(
                _(
                    "DocType '{0}' is a child table and cannot be targeted directly. Trigger on its parent DocType instead."
                ).format(name)
            )
        if meta.issingle:
            frappe.throw(_("DocType '{0}' is a Single DocType and cannot be targeted.").format(name))

        # Event
        if self.doctype_event and self.doctype_event not in VALID_EVENTS:
            frappe.throw(_("Invalid doctype_event: {0}").format(self.doctype_event))

        # changed_fields only valid on on_update
        if self.changed_fields and self.doctype_event != "on_update":
            frappe.throw(_("changed_fields is only valid when doctype_event is 'on_update'."))

        # Filters
        if self.filters:
            valid_fieldnames = {f.fieldname for f in meta.fields}
            # Include the standard metadata fields we advertise in get_doctype_fields
            valid_fieldnames.update(
                {
                    "name",
                    "owner",
                    "creation",
                    "modified",
                    "modified_by",
                    "docstatus",
                }
            )
            for row in self.filters:
                if not row.fieldname:
                    frappe.throw(_("Filter rows must have a fieldname."))
                if not row.operator:
                    frappe.throw(_("Filter rows must have an operator."))
                if row.fieldname not in valid_fieldnames:
                    frappe.throw(_("Filter field '{0}' is not a field of '{1}'.").format(row.fieldname, name))

    def on_update(self):
        _invalidate_trigger_map()

    def on_trash(self):
        _invalidate_trigger_map()
