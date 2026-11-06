// The records here hold a page's code, so a user who is not a System Manager sees only their own
// personal pages. The pages they can open, shared ones included, are listed at /app/fac-pages.
frappe.listview_settings["FAC Page"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Open pages"), () => frappe.set_route("fac-pages"));
	},
};
