// The frappe a Shared page's script gets in Desk. Keep this first line a comment: fac_pages.js
// inlines the file through Frappe's render_include from a line that starts with "//".
//
// Desk's frappe.format returns html, such as <div style='text-align: right'>₹ 79,360.00</div>, so
// a page that escapes a formatted amount, as it must in the chat panel, would show the tags. A page
// gets Desk's frappe with one change: format returns the text a number, an amount, a date or a
// duration shows, as the chat panel's does (chat/frontend/src/utils/pageFormat.js). Every other
// member is Desk's own. Tested by chat/frontend/src/widget/desk/facPageFrappe.spec.js, which runs
// this file and fac_pages.js.

// Desk's formatters whose output holds no text from the record, only digits, the site's currency
// symbol, a date or a duration (frappe/public/js/frappe/form/formatters.js).
const FAC_PAGE_PLAIN_FIELDTYPES = ["Currency", "Float", "Int", "Percent", "Date", "Datetime", "Time", "Duration"];

// eslint-disable-next-line no-unused-vars
function fac_page_frappe(desk_frappe) {
	const format = (value, df, options, doc) => fac_page_plain_format(desk_frappe.format(value, df, options, doc), df);
	return new Proxy(desk_frappe, {
		get(target, key) {
			return key === "format" ? format : target[key];
		},
	});
}

// Any other fieldtype's output is Desk's own, unchanged: it can hold record text that Desk escaped,
// and its text content would unescape it. A text that holds "<" is not a plain figure (a custom
// formatter, say), so it is left as Desk gave it too. Parsed in a detached document that is never
// shown, so nothing in it runs or loads.
function fac_page_plain_format(html, df) {
	const fieldtype = String((df && df.fieldtype) || "Data").replace(/ /g, "");
	if (!FAC_PAGE_PLAIN_FIELDTYPES.includes(fieldtype) || typeof html !== "string") return html;
	const text = new DOMParser().parseFromString(html, "text/html").body.textContent;
	return text.includes("<") ? html : text;
}
