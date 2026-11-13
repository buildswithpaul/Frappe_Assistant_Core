/**
 * `fac.report(name, filters)`: a FAC Page reads a report's figures through this one helper, in
 * Desk, beside the chat and in a personal page's frame alike (bundled with fac.chart,
 * vite.pagecharts.config.js).
 *
 * It asks report_access first: in Desk a refused query_report.run opens the "Not permitted"
 * dialog and leaves the page, so a report the viewer may not run is never called. It then
 * returns the report as a page draws it: data rows as dicts, the report's own total row and
 * summary, and a status for a report still being prepared or one the server refused to run.
 * Both calls are silent, so Desk never opens its message dialog over the page.
 */

const ACCESS_METHOD = "frappe_assistant_core.api.fac_page.report_access";
const RUN_METHOD = "frappe.desk.query_report.run";

// A financial statement's summary lines, such as 'Total Income (Credit)' and 'Profit for the
// year', come back with their account name wrapped in single quotes.
const QUOTED = /^'(.*)'$/;

const emptyResult = (status, message = null) => ({
	status,
	columns: [],
	rows: [],
	total: null,
	summary: [],
	chart: null,
	message,
});

const isBlank = (row) => Object.values(row).every((value) => value == null || value === "");

function unquoted(row) {
	const match = typeof row.account === "string" && row.account.match(QUOTED);
	if (!match) return row;
	const name = typeof row.account_name === "string" ? row.account_name.replace(QUOTED, "$1") : row.account_name;
	return { ...row, account: match[1], account_name: name, total_line: true };
}

// The text of a refused run: the chat's transports set message or userMessage; Desk rejects with
// its jqXHR, whose response carries the server's messages.
function failureMessage(error) {
	const text = error?.userMessage || error?.message;
	if (text) return String(text);
	try {
		const messages = JSON.parse(error?.responseJSON?._server_messages || "[]");
		const first = messages.length ? JSON.parse(messages[0]) : null;
		return first ? String(first.message || first) : null;
	} catch {
		return null;
	}
}

// A report's total row is an array aligned with its columns; every other row is a dict.
function totalRow(row, columns) {
	return Object.fromEntries(columns.map((column, i) => [column.fieldname, row[i]]));
}

/**
 * Read `reportName` with `filters` as the viewer.
 *
 * @param {object} frappe the page's frappe: Desk's, the chat panel's stand-in or the frame's
 * @returns {Promise<{status: "ok"|"preparing"|"no_access"|"error", columns: object[], rows: object[],
 *   total: object|null, summary: object[], chart: object|null, message: string|null}>}
 */
export async function report(frappe, reportName, filters = {}) {
	const access = await frappe.call({ method: ACCESS_METHOD, type: "GET", args: { reports: [reportName] }, silent: true });
	if (!access.message?.[reportName]) return emptyResult("no_access");

	let data;
	try {
		const r = await frappe.call({ method: RUN_METHOD, type: "GET", args: { report_name: reportName, filters }, silent: true });
		data = r.message || {};
	} catch (error) {
		const status = Number(error?.status);
		if (status === 403) return emptyResult("no_access");
		// The server answered and refused, such as a filter value the viewer may not read or a
		// missing mandatory filter: the page says why instead of leaving the card empty.
		if (status) return emptyResult("error", failureMessage(error));
		throw error;
	}
	// A completed Prepared Report comes back with its rows and its doc; only one with no doc has none.
	if (data.prepared_report && !data.doc) return emptyResult("preparing", data.message || null);

	const columns = data.columns || [];
	const rows = [];
	let total = null;
	for (const row of data.result || []) {
		if (Array.isArray(row)) total = totalRow(row, columns);
		else if (row && !isBlank(row)) rows.push(unquoted(row));
	}
	return {
		status: "ok",
		columns,
		rows,
		total,
		summary: data.report_summary || [],
		chart: data.chart || null,
		message: data.message || null,
	};
}
