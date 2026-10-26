import { describe, expect, it } from "vitest";

import { describePageRequest, fitsCurrentDoc, mayTrustForPage, normalisePayload } from "./pageRequestPrompt";

const names = (request) => request.fields.map((f) => f.name);

describe("describePageRequest: every field, in full", () => {
	it("lists every field an insert sets, however many, with values in full", () => {
		const doc = { doctype: "ToDo" };
		for (let i = 0; i < 12; i++) doc[`f${i}`] = `value ${i}`;
		doc.description = "x".repeat(300);
		const request = describePageRequest("frappe.client.insert", normalisePayload("frappe.client.insert", { doc }));
		expect(request.message).toBe("This page wants to create a new ToDo with these fields.");
		expect(request.fields).toHaveLength(13);
		expect(request.fields.at(-1)).toEqual({ name: "description", value: "x".repeat(300) });
	});

	it("lists a child table's rows and their fields, hiding only each row's position", () => {
		const doc = {
			doctype: "Journal Entry",
			accounts: [
				{ idx: 1, account: "Cash", debit: 500, parent: "JV-1", parentfield: "accounts" },
				{ idx: 2, account: "Bank", credit: 500 },
			],
		};
		const [field] = describePageRequest("frappe.client.insert", normalisePayload("frappe.client.insert", { doc })).fields;
		expect(field.name).toBe("accounts");
		expect(field.rows).toEqual([
			[
				{ name: "account", value: "Cash" },
				{ name: "debit", value: "500" },
				{ name: "parent", value: "JV-1" },
				{ name: "parentfield", value: "accounts" },
			],
			[
				{ name: "account", value: "Bank" },
				{ name: "credit", value: "500" },
			],
		]);
	});

	it("shows a top-level idx, and hides only keys the server assigns", () => {
		const doc = { doctype: "ToDo", idx: 4, creation: "x", modified: "y", modified_by: "z", _user_tags: "t", status: "Open" };
		expect(names(describePageRequest("frappe.client.insert", { doc }))).toEqual(["idx", "status"]);
	});

	it("leaves hidden characters out of what it shows, and says they were there", () => {
		const request = describePageRequest("frappe.client.set_value", {
			doctype: "ToDo",
			name: "TD-1",
			fieldname: { description: "pay ‮redro‬ now​" },
		});
		expect(request.fields[0].value).toBe("pay redro now");
		expect(request.hiddenChars).toBe(true);
		expect(describePageRequest("frappe.client.delete", { doctype: "ToDo", name: "TD-1" }).hiddenChars).toBe(false);
	});

	it("describes a method call with every value it carries", () => {
		const request = describePageRequest("sales_feed", { months: 6, filters: { region: "India" } });
		expect(request.message).toBe("This page wants to run sales_feed with these values.");
		expect(request.fields).toEqual([
			{ name: "months", value: "6" },
			{ name: "filters", value: '{"region":"India"}' },
		]);
	});
});

describe("describePageRequest: save and submit against the record as it is", () => {
	const current = {
		doctype: "ToDo",
		name: "TD-1",
		docstatus: 0,
		modified: "2026-10-26",
		status: "Open",
		description: "Call Blue Harbor",
		allocated_to: "avery@example.com",
		roles: [{ role: "a" }, { role: "b" }],
		owner: "avery@example.com",
	};

	it("shows each field before and after, and what the save would clear or empty", () => {
		const payload = normalisePayload("frappe.client.save", { doc: { doctype: "ToDo", name: "TD-1", status: "Closed", description: "Call Blue Harbor" } });
		const request = describePageRequest("frappe.client.save", payload, current);
		expect(request.message).toBe("This page wants to save ToDo TD-1. The record will hold exactly these fields.");
		expect(request.fields).toEqual([
			{ name: "status", value: "Closed", before: "Open", status: "changed" },
			{ name: "description", value: "Call Blue Harbor", before: "Call Blue Harbor", status: "same" },
			{ name: "allocated_to", value: "", before: "avery@example.com", beforeRows: undefined, status: "blanked" },
			{ name: "roles", value: "", before: "", beforeRows: 2, status: "emptied" },
		]);
	});

	it("lists a submit's fields the same way, and says it can't be undone", () => {
		const payload = normalisePayload("frappe.client.submit", { doc: { doctype: "ToDo", name: "TD-1", status: "Closed" } });
		const request = describePageRequest("frappe.client.submit", payload, current);
		expect(request.message).toBe("This page wants to submit ToDo TD-1 with these fields. Submitting can't be undone.");
		expect(request.fields[0]).toEqual({ name: "status", value: "Closed", before: "Open", status: "changed" });
		expect(names(request)).toContain("allocated_to");
	});

	it("refuses a save that would change the record's docstatus", () => {
		const payload = normalisePayload("frappe.client.save", { doc: { doctype: "ToDo", name: "TD-1", status: "x" } });
		expect(fitsCurrentDoc("frappe.client.save", payload, { docstatus: 1 })).toBe(false);
		expect(fitsCurrentDoc("frappe.client.save", payload, { docstatus: 0 })).toBe(true);
	});
});

describe("normalisePayload", () => {
	it("reads set_value's fieldname the way Frappe does, so what is shown is what runs", () => {
		const fromJson = normalisePayload("frappe.client.set_value", {
			doctype: "ToDo",
			name: "T1",
			fieldname: '{"description":"x","allocated_to":"someone@example.com"}',
		});
		expect(fromJson).toEqual({
			doctype: "ToDo",
			name: "T1",
			fieldname: { description: "x", allocated_to: "someone@example.com" },
		});
		// A falsy value sets the field to "", as frappe/client.py does.
		expect(normalisePayload("frappe.client.set_value", { doctype: "ToDo", name: "T1", fieldname: "status", value: 0 }).fieldname).toEqual({ status: "" });
		expect(normalisePayload("frappe.client.set_value", { doctype: "ToDo", name: "T1", fieldname: "status", value: "Closed" }).fieldname).toEqual({ status: "Closed" });
		expect(normalisePayload("frappe.client.set_value", { doctype: "ToDo", name: "T1", fieldname: "[1, 2]" })).toBe(null);
	});

	it("takes a write's record only from its doc, and refuses a top level that disagrees", () => {
		const doc = { doctype: "ToDo", name: "TD-1", status: "Closed" };
		expect(normalisePayload("frappe.client.save", { doc: JSON.stringify(doc) }).doc).toEqual(doc);
		expect(normalisePayload("frappe.client.save", { doc, doctype: "Note" })).toBe(null);
		expect(normalisePayload("frappe.client.save", { doc, name: "TD-2" })).toBe(null);
		expect(normalisePayload("frappe.client.insert", { doc: { status: "x" } })).toBe(null);
		expect(normalisePayload("frappe.client.save", { doc: { doctype: "ToDo" } })).toBe(null);
	});

	it("refuses an insert or save that is not a draft", () => {
		for (const method of ["frappe.client.insert", "frappe.client.save"]) {
			expect(normalisePayload(method, { doc: { doctype: "ToDo", name: "TD-1", docstatus: 1 } })).toBe(null);
			expect(normalisePayload(method, { doc: { doctype: "ToDo", name: "TD-1", docstatus: 0 } })).not.toBe(null);
		}
	});

	it("refuses an insert or save that sets whose record it is or where it hangs", () => {
		for (const key of ["owner", "parent", "parenttype", "parentfield"]) {
			for (const method of ["frappe.client.insert", "frappe.client.save"]) {
				expect(normalisePayload(method, { doc: { doctype: "ToDo", name: "TD-1", [key]: "x" } }), `${method} ${key}`).toBe(null);
			}
		}
	});
});

describe("mayTrustForPage", () => {
	it("offers Allow for this page only for a Server Script API method", () => {
		expect(mayTrustForPage("sales_feed")).toBe(true);
		for (const method of [
			"frappe.desk.form.save.savedocs",
			"frappe.client.insert_many",
			"frappe.client.bulk_update",
			"frappe.client.rename_doc",
			"frappe.desk.reportview.delete_items",
			"frappe.model.workflow.apply_workflow",
			"erpnext.anything.at_all",
			"my_app.api.feed",
			"run_doc_method",
			"runserverobj",
			"logout",
		]) {
			expect(mayTrustForPage(method), method).toBe(false);
		}
	});

	it("tells the user what Allow for this page covers", () => {
		expect(describePageRequest("sales_feed", {}).note).toBe(
			"Allow for this page lets this version of the page run sales_feed again without asking.",
		);
		expect(describePageRequest("frappe.desk.form.save.savedocs", {}).note).toBe("");
	});
});
