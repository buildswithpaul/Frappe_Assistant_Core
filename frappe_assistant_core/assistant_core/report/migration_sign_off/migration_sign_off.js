// Frappe Assistant Core - AI Assistant integration for Frappe Framework
// Copyright (C) 2025 Paul Clinton
// License: GNU Affero General Public License v3 or later

frappe.query_reports["Migration Sign-off"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("Sessions Started From"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("Sessions Started To"),
			fieldtype: "Date",
		},
		{
			fieldname: "migration_plan",
			label: __("Migration Plan"),
			fieldtype: "Data",
			description: __("A migration plan's id: its files only, whatever the dates."),
		},
		{
			fieldname: "import_session",
			label: __("Import Sessions"),
			fieldtype: "Data",
			description: __("Session ids, comma separated. Leave blank for every session of the user."),
		},
		{
			fieldname: "user",
			label: __("User"),
			fieldtype: "Link",
			options: "User",
			default: frappe.session.user,
		},
		{
			fieldname: "document",
			label: __("Message as a Document (for the PDF)"),
			fieldtype: "Check",
		},
	],
};
