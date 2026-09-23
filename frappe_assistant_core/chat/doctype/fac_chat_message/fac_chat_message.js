// Frappe Assistant Core - AI Assistant integration for Frappe Framework
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

frappe.ui.form.on("FAC Chat Message", {
	refresh(frm) {
		// Make form read-only for most users (messages shouldn't be edited)
		if (!frappe.user.has_role("System Manager")) {
			frm.disable_form();
		}

		// Add button to view full session
		if (frm.doc.session_id) {
			frm.add_custom_button(__("View Full Session"), () => {
				frappe.set_route("List", "FAC Chat Message", {
					session_id: frm.doc.session_id,
				});
			});
		}

		// Format content display for better readability
		if (frm.doc.content) {
			frm.fields_dict.content.$wrapper.find("textarea").css({
				"font-family": "monospace",
				"white-space": "pre-wrap",
			});
		}
	},
});
