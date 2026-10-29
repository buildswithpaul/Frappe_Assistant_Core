// The frappe a Shared page's script gets in Desk. Keep this first line a comment: fac_pages.js
// inlines the file through Frappe's render_include from a line that starts with "//".
//
// Desk's frappe.format returns html, such as <div style='text-align: right'>₹ 79,360.00</div>, so
// a page that escapes it, as it must in the chat panel, would show the tags. A page gets Desk's
// frappe with one change: its format returns the text that html shows, as the chat panel's does
// (chat/frontend/src/utils/pageFormat.js). Every other member is Desk's own. Tested by
// chat/frontend/src/widget/desk/facPageFrappe.spec.js, which runs this file and fac_pages.js.

// eslint-disable-next-line no-unused-vars
function fac_page_frappe(desk_frappe) {
	// Parsed in a detached document that is never shown: no script in it runs and nothing loads.
	const text = (html) =>
		html == null ? "" : new DOMParser().parseFromString(String(html), "text/html").body.textContent;
	const format = (value, df, options, doc) => text(desk_frappe.format(value, df, options, doc));
	return new Proxy(desk_frappe, {
		get(target, key) {
			return key === "format" ? format : target[key];
		},
	});
}
