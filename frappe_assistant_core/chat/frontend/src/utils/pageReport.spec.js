import { describe, expect, it } from "vitest";

import { report } from "./pageReport";

const ACCESS = "frappe_assistant_core.api.fac_page.report_access";
const RUN = "frappe.desk.query_report.run";

// Shapes query_report.run returned on Frappe v16 / ERPNext 16 (Profit and Loss Statement,
// Accounts Receivable, and a Prepared Report with no result yet).
const PL_FIXTURE = {
	columns: [
		{ fieldname: "account", label: "Account", fieldtype: "Link", options: "Account" },
		{ fieldname: "nov_2026", label: "Nov 2026", fieldtype: "Currency", options: "currency" },
		{ fieldname: "total", label: "Total", fieldtype: "Currency", options: "currency" },
	],
	result: [
		{ account: "Direct Income - C", account_name: "Direct Income", indent: 1.0, parent_account: "Income - C", is_group: 1, nov_2026: 2020812.67, total: 2020812.67 },
		{ account: "'Total Income (Credit)'", account_name: "'Total Income (Credit)'", indent: null, nov_2026: 2020812.67, total: 2020812.67 },
		{ account: null, account_name: null, indent: null, nov_2026: null, total: null },
		{ account: "'Profit for the year'", account_name: "'Profit for the year'", indent: null, nov_2026: 2020813.47, total: 2020813.47 },
	],
	report_summary: [
		{ value: 2020812.67, label: "Total Income", datatype: "Currency", currency: "INR" },
		{ value: -0.8, label: "Total Expense", datatype: "Currency", currency: "INR" },
		{ value: 2020813.47, indicator: "Green", label: "Net Profit", datatype: "Currency", currency: "INR" },
	],
	chart: { data: { labels: ["Nov 2026"] } },
	message: null,
	add_total_row: 0,
};

const AR_FIXTURE = {
	columns: [
		{ fieldname: "party", label: "Customer", fieldtype: "Dynamic Link" },
		{ fieldname: "outstanding", label: "Outstanding Amount", fieldtype: "Currency" },
		{ fieldname: "currency", label: "Currency", fieldtype: "Link" },
	],
	result: [
		{ party: "Acme", outstanding: 1228000.0, currency: "INR" },
		{ party: "Globex", outstanding: 645899.0, currency: "INR" },
		["", 1873899.0, "INR"],
	],
	report_summary: null,
	add_total_row: true,
};

function fakeFrappe({ access = {}, run = PL_FIXTURE, runError = null } = {}) {
	const calls = [];
	return {
		calls,
		argsFor: (method) => calls.find((c) => c.method === method)?.args,
		call(opts) {
			calls.push(opts);
			if (opts.method === ACCESS) {
				const names = opts.args.reports;
				return Promise.resolve({ message: Object.fromEntries(names.map((n) => [n, access[n] ?? true])) });
			}
			if (opts.method === RUN) return runError ? Promise.reject(runError) : Promise.resolve({ message: run });
			return Promise.reject(new Error(`unexpected ${opts.method}`));
		},
	};
}

describe("report", () => {
	it("returns no_access without running a report the viewer may not run", async () => {
		const f = fakeFrappe({ access: { "Profit and Loss Statement": false } });
		const r = await report(f, "Profit and Loss Statement", { company: "C" });
		expect(r.status).toBe("no_access");
		expect(f.calls.map((c) => c.method)).not.toContain(RUN);
	});

	it("reports preparing for a prepared report with no result", async () => {
		const r = await report(fakeFrappe({ run: { prepared_report: true, doc: null, add_total_row: true } }), "Stock Balance");
		expect(r).toMatchObject({ status: "preparing", rows: [], total: null, columns: [] });
	});

	it("maps the array total row to a dict and keeps it out of rows", async () => {
		const r = await report(fakeFrappe({ run: AR_FIXTURE }), "Accounts Receivable");
		expect(r.total).toMatchObject({ outstanding: 1873899.0, currency: "INR" });
		expect(r.rows).toHaveLength(2);
		expect(r.rows.every((row) => !Array.isArray(row))).toBe(true);
	});

	it("unquotes P&L summary lines, marks them, and drops blank separators", async () => {
		const r = await report(fakeFrappe(), "Profit and Loss Statement");
		const profit = r.rows.find((row) => row.account === "Profit for the year");
		expect(profit).toMatchObject({ total_line: true, total: 2020813.47, account_name: "Profit for the year" });
		expect(r.rows.find((row) => row.account === "Direct Income - C").total_line).toBeUndefined();
		expect(r.rows.some((row) => Object.values(row).every((v) => v == null))).toBe(false);
		expect(r.summary.map((s) => s.label)).toEqual(["Total Income", "Total Expense", "Net Profit"]);
		expect(r).toMatchObject({ status: "ok", total: null, chart: PL_FIXTURE.chart });
		expect(r.columns.map((c) => c.fieldname)).toEqual(["account", "nov_2026", "total"]);
	});

	it("passes filters through as an object on a GET", async () => {
		const f = fakeFrappe();
		await report(f, "Profit and Loss Statement", { company: "C", cost_center: ["Main - C"] });
		const run = f.calls.find((c) => c.method === RUN);
		expect(run.type).toBe("GET");
		expect(run.args).toEqual({ report_name: "Profit and Loss Statement", filters: { company: "C", cost_center: ["Main - C"] } });
		expect(f.argsFor(ACCESS)).toEqual({ reports: ["Profit and Loss Statement"] });
	});

	it("returns no_access when the run itself is refused with 403", async () => {
		const r = await report(fakeFrappe({ runError: { status: 403 } }), "Profit and Loss Statement");
		expect(r.status).toBe("no_access");
	});

	it("reads a prepared report whose result has been generated", async () => {
		// query_report.run adds prepared_report and the Prepared Report's doc to a completed result.
		const r = await report(fakeFrappe({ run: { ...AR_FIXTURE, prepared_report: true, doc: { name: "PR-0001" } } }), "Accounts Receivable");
		expect(r.status).toBe("ok");
		expect(r.rows).toHaveLength(2);
		expect(r.total).toMatchObject({ outstanding: 1873899.0 });
	});

	it("returns error with the server's message when a run is refused on a filter value", async () => {
		// validate_filters_permissions throws a ValidationError (HTTP 417) for a company the viewer cannot read.
		const refused = Object.assign(new Error("You do not have access to Company C"), { status: 417 });
		const r = await report(fakeFrappe({ runError: refused }), "Profit and Loss Statement", { company: "C" });
		expect(r).toMatchObject({ status: "error", message: "You do not have access to Company C", rows: [] });
	});

	it("asks Desk not to open its message dialog over the page", async () => {
		const f = fakeFrappe();
		await report(f, "Profit and Loss Statement");
		expect(f.calls.map((c) => c.silent)).toEqual([true, true]);
	});

	it("rethrows any other failure so the host can report it", async () => {
		await expect(report(fakeFrappe({ runError: new Error("boom") }), "Profit and Loss Statement")).rejects.toThrow("boom");
	});
});
