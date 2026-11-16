// Frappe Assistant Core - AI Assistant integration for Frappe Framework
// Copyright (C) 2025 Paul Clinton
// License: GNU Affero General Public License v3 or later

frappe.query_reports["Import Sessions"] = {
	filters: [
		{ fieldname: "stuck_only", label: __("Stuck Only"), fieldtype: "Check" },
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: [
				"",
				"File Read",
				"Mapped",
				"Dry Run Failed",
				"Ready to Import",
				"Importing",
				"Completed",
				"Partially Completed",
				"Failed",
				"Cancelled",
				"Undone",
			].join("\n"),
		},
		{ fieldname: "user", label: __("User"), fieldtype: "Link", options: "User" },
	],
};
