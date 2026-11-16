import { describe, expect, it } from "vitest";

import { createPageReach } from "./pageReach";

// get_page's withheld for a user who is not a System Manager (core/field_access.py withheld_from_assistant).
const WITHHELD = {
	fields: ["bank_account_no", "iban"],
	doctypes: { User: ["last_login"] },
	hidden_doctypes: ["System Settings"],
};
const NOTHING = { fields: [], doctypes: {}, hidden_doctypes: [] };

async function reachAfter(withheld, calls) {
	const reach = createPageReach(withheld);
	for (const [method, args, answer] of calls) {
		const request = answer instanceof Error ? Promise.reject(answer) : Promise.resolve(answer);
		await reach.watch(method, args, request).catch(() => {});
	}
	return reach.shown();
}

describe("createPageReach", () => {
	it("cannot tell what a page shows without get_page's withheld, so an older server always asks", async () => {
		expect(await reachAfter(undefined, [])).toBeNull();
	});

	it("shows nothing hidden for a viewer FAC hides nothing from", async () => {
		const shown = await reachAfter(NOTHING, [
			["frappe.client.get", { doctype: "Bank Account", name: "B-1" }, { iban: "DE89" }],
			["my_app.api.anything", {}, "text"],
		]);
		expect(shown).toEqual({ fields: [], methods: [] });
	});

	it("names a hidden field a read returned with a value", async () => {
		const shown = await reachAfter(WITHHELD, [
			["frappe.client.get", { doctype: "Bank Account", name: "B-1" }, { name: "B-1", iban: "DE89", bank_account_no: "" }],
		]);
		expect(shown).toEqual({ fields: ["iban"], methods: [] });
	});

	it("finds hidden fields in rows of a list", async () => {
		const shown = await reachAfter(WITHHELD, [
			["frappe.client.get_list", { doctype: "Bank Account", fields: '["*"]' }, [{ name: "B-1" }, { name: "B-2", bank_account_no: "123" }]],
		]);
		expect(shown.fields).toEqual(["bank_account_no"]);
	});

	it("checks a doctype's own hidden fields only on reads of that doctype", async () => {
		const other = await reachAfter(WITHHELD, [["frappe.client.get", { doctype: "Customer", name: "C" }, { last_login: "x" }]]);
		const user = await reachAfter(WITHHELD, [["frappe.client.get", { doctype: "User", name: "u" }, { last_login: "x" }]]);
		expect(other.fields).toEqual([]);
		expect(user.fields).toEqual(["last_login"]);
	});

	it("names a doctype hidden whole once a read of it succeeds", async () => {
		const shown = await reachAfter(WITHHELD, [
			["frappe.client.get_single_value", { doctype: "System Settings", field: "country" }, "India"],
		]);
		expect(shown.fields).toEqual(["System Settings"]);
	});

	it("finds a hidden field that is a report's column", async () => {
		const shown = await reachAfter(WITHHELD, [
			[
				"frappe.desk.query_report.run",
				{ report_name: "Supplier Bank" },
				{ columns: [{ fieldname: "supplier" }, { fieldname: "iban", label: "IBAN" }], result: [["S-1", "DE89"]] },
			],
		]);
		expect(shown.fields).toEqual(["iban"]);
	});

	it("finds a hidden field among a list view's keys", async () => {
		const shown = await reachAfter(WITHHELD, [
			["frappe.desk.reportview.get", { doctype: "Bank Account" }, { keys: ["name", "iban"], values: [["B-1", "DE89"]] }],
		]);
		expect(shown.fields).toEqual(["iban"]);
	});

	it("names any method outside Frappe's reads and record writes, since its answer can't be checked", async () => {
		const shown = await reachAfter(WITHHELD, [
			["frappe.client.get_count", { doctype: "ToDo" }, 3],
			["frappe.client.set_value", { doctype: "ToDo", name: "T", fieldname: "status", value: "Closed" }, { name: "T" }],
			["my_app.api.balances", {}, "DE89 3704"],
		]);
		expect(shown).toEqual({ fields: [], methods: ["my_app.api.balances"] });
	});

	it("counts nothing from a call that failed", async () => {
		const shown = await reachAfter(WITHHELD, [
			["frappe.client.get", { doctype: "System Settings" }, new Error("Not permitted")],
			["my_app.api.balances", {}, new Error("Not permitted")],
		]);
		expect(shown).toEqual({ fields: [], methods: [] });
	});

	it("hands the call's own answer and failure back unchanged", async () => {
		const reach = createPageReach(WITHHELD);
		const answer = { iban: "DE89" };
		await expect(reach.watch("frappe.client.get", { doctype: "Bank Account" }, Promise.resolve(answer))).resolves.toBe(answer);
		const failure = new Error("Not permitted");
		await expect(reach.watch("frappe.client.get", {}, Promise.reject(failure))).rejects.toBe(failure);
	});
});
