// Frappe Assistant Core - AI Assistant integration for Frappe Framework
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify it under
// the terms of the GNU Affero General Public License as published by the Free
// Software Foundation, either version 3 of the License, or (at your option) any
// later version. See https://www.gnu.org/licenses/.
//
// An import session's form (#34542): only the import tools change a session, so the one action here
// is Release, for a System Manager, on a session stuck importing or a plan nothing runs. The server
// checks the role and that no job is still running it.

frappe.ui.form.on("FAC Import Session", {
	refresh(frm) {
		const stuck = frm.doc.status === "Importing" || frm.doc.plan_status === "Running";
		if (!stuck || !frappe.user.has_role("System Manager")) return;
		frm.add_custom_button(__("Release"), () =>
			frappe.prompt(
				[
					{
						fieldname: "reason",
						fieldtype: "Small Text",
						label: __("Why is it released?"),
						reqd: 1,
						description: __("It goes in the session's step log. What was imported stays."),
					},
				],
				(values) =>
					frm.call("release", { reason: values.reason }).then(() => {
						frappe.show_alert({ message: __("Released."), indicator: "orange" });
						frm.reload_doc();
					}),
				__("Release {0}", [frm.doc.name]),
				__("Release")
			)
		);
	},
});
