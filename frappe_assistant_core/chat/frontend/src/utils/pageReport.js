/**
 * `fac.report(name, filters)`: a FAC Page reads a report's figures through this one helper, in
 * Desk, beside the chat and in a personal page's frame alike (bundled with fac.chart,
 * vite.pagecharts.config.js).
 *
 * It asks report_access first: in Desk a refused query_report.run opens the "Not permitted"
 * dialog and leaves the page, so a report the viewer may not run is never called. It then
 * returns the report as a page draws it: data rows as dicts, the report's own total row and
 * summary, and a status for a report still being prepared.
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

// A report's total row is an array aligned with its columns; every other row is a dict.
function totalRow(row, columns) {
	return Object.fromEntries(columns.map((column, i) => [column.fieldname, row[i]]));
}

/**
 * Read `reportName` with `filters` as the viewer.
 *
 * @param {object} frappe the page's frappe: Desk's, the chat panel's stand-in or the frame's
 * @returns {Promise<{status: "ok"|"preparing"|"no_access", columns: object[], rows: object[],
 *   total: object|null, summary: object[], chart: object|null, message: string|null}>}
 */
export async function report(frappe, reportName, filters = {}) {
	const access = await frappe.call({ method: ACCESS_METHOD, type: "GET", args: { reports: [reportName] } });
	if (!access.message?.[reportName]) return emptyResult("no_access");

	let data;
	try {
		const r = await frappe.call({ method: RUN_METHOD, type: "GET", args: { report_name: reportName, filters } });
		data = r.message || {};
	} catch (error) {
		if (Number(error?.status) === 403) return emptyResult("no_access");
		throw error;
	}
	if (data.prepared_report) return emptyResult("preparing", data.message || null);

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
