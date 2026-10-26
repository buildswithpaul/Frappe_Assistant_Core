import { describe, expect, it } from "vitest";

import {
	describePageRequest,
	fitsCurrentDoc,
	isMethodName,
	mayTrustForPage,
	mergeWithCurrent,
	normalisePayload,
} from "./pageRequestPrompt";

const names = (request) => request.fields.map((f) => f.name);
const insert = (doc) => normalisePayload("frappe.client.insert", { doc });

describe("describePageRequest: every field, in full", () => {
	it("lists every field an insert sets, however many, with values in full", () => {
		const doc = { doctype: "ToDo" };
		for (let i = 0; i < 12; i++) doc[`f${i}`] = `value ${i}`;
		doc.description = "x".repeat(300);
		const request = describePageRequest("frappe.client.insert", insert(doc));
		expect(request.message).toBe("This page wants to create a new ToDo with these fields.");
		expect(request.fields).toHaveLength(13);
		expect(request.fields.at(-1)).toEqual({ name: "description", value: "x".repeat(300) });
	});

	it("names the record an insert creates", () => {
		const request = describePageRequest("frappe.client.insert", insert({ doctype: "ToDo", __newname: "TD-OURS", status: "Open" }));
		expect(request.message).toBe("This page wants to create a new ToDo named TD-OURS with these fields.");
		expect(names(request)).toEqual(["status"]);
	});

	it("lists a child table's rows and their fields, leaving out only each row's position", () => {
		const doc = {
			doctype: "Journal Entry",
			accounts: [
				{ idx: 1, account: "Cash", debit: 500 },
				{ idx: 2, account: "Bank", credit: 500 },
			],
		};
		const [field] = describePageRequest("frappe.client.insert", insert(doc)).fields;
		expect(field.rows).toEqual([
			[
				{ name: "account", value: "Cash" },
				{ name: "debit", value: "500" },
			],
			[
				{ name: "account", value: "Bank" },
				{ name: "credit", value: "500" },
			],
		]);
	});

	it("shows every key but the client's own flags and modified", () => {
		const doc = { doctype: "ToDo", idx: 4, docstatus: 0, __islocal: 1, __unsaved: 1, modified: "y", status: "Open" };
		expect(names(describePageRequest("frappe.client.insert", insert(doc)))).toEqual(["idx", "docstatus", "status"]);
	});

	it("leaves hidden characters out of what it shows, and says they were there", () => {
		const request = describePageRequest("frappe.client.set_value", {
			doctype: "ToDo",
			name: "TD-1",
			fieldname: { description: "pay \u202Eredro\u202C now\u200B" },
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

describe("save and submit: the record as it is, with the page's changes over it", () => {
	const current = {
		doctype: "ToDo",
		name: "TD-1",
		docstatus: 0,
		owner: "avery@example.com",
		creation: "2026-10-01 10:00:00",
		modified: "2026-10-26 09:00:00",
		modified_by: "avery@example.com",
		_assign: '["avery@example.com"]',
		status: "Open",
		description: "Call Blue Harbor",
		allocated_to: "avery@example.com",
		roles: [{ role: "a" }, { role: "b" }],
	};

	it("sends every field the page left out as it is now, owner and creation included", () => {
		const payload = normalisePayload("frappe.client.save", { doc: { doctype: "ToDo", name: "TD-1", status: "Closed" } });
		const merged = mergeWithCurrent(payload, current);
		expect(merged.doc).toEqual({ ...current, status: "Closed" });
	});

	it("shows only what changes, before and after, and says everything else keeps its value", () => {
		const payload = normalisePayload("frappe.client.save", {
			doc: { doctype: "ToDo", name: "TD-1", status: "Closed", description: "", roles: [{ role: "a" }] },
		});
		const request = describePageRequest("frappe.client.save", mergeWithCurrent(payload, current), current);
		expect(request.message).toBe(
			"This page wants to save ToDo TD-1. These fields change; every other field keeps its current value.",
		);
		expect(request.fields).toEqual([
			{ name: "status", value: "Closed", before: "Open", status: "changed" },
			{ name: "description", value: "", before: "Call Blue Harbor", status: "blanked" },
			{ name: "roles", value: "", rows: [[{ name: "role", value: "a" }]], status: "changed", beforeRows: 2 },
		]);
	});

	it("describes a submit the same way, and says it can't be undone", () => {
		const payload = normalisePayload("frappe.client.submit", { doc: { doctype: "ToDo", name: "TD-1", status: "Closed" } });
		const request = describePageRequest("frappe.client.submit", mergeWithCurrent(payload, current), current);
		expect(request.message).toMatch(/Submitting can't be undone\.$/);
		expect(request.fields).toEqual([{ name: "status", value: "Closed", before: "Open", status: "changed" }]);
	});

	it("refuses a save that changes docstatus, a submit that is not of a draft, and server keys that differ", () => {
		const doc = { doctype: "ToDo", name: "TD-1" };
		expect(fitsCurrentDoc("frappe.client.save", { ...doc, docstatus: 1 }, current)).toBe(false);
		expect(fitsCurrentDoc("frappe.client.save", doc, { ...current, docstatus: 1 })).toBe(true);
		expect(fitsCurrentDoc("frappe.client.submit", doc, { ...current, docstatus: 1 })).toBe(false);
		expect(fitsCurrentDoc("frappe.client.save", { ...doc, owner: "someone@example.com" }, current)).toBe(false);
		expect(fitsCurrentDoc("frappe.client.save", { ...doc, creation: "2020-01-01" }, current)).toBe(false);
		expect(fitsCurrentDoc("frappe.client.save", { ...doc, modified_by: "x@example.com" }, current)).toBe(false);
		expect(fitsCurrentDoc("frappe.client.save", { ...doc, owner: current.owner }, current)).toBe(true);
	});
});

describe("normalisePayload", () => {
	it("reads set_value's fieldname the way Frappe does, so what is shown is what runs", () => {
		const fromJson = normalisePayload("frappe.client.set_value", {
			doctype: "ToDo",
			name: "T1",
			fieldname: '{"description":"x","allocated_to":"someone@example.com"}',
		});
		expect(fromJson.fieldname).toEqual({ description: "x", allocated_to: "someone@example.com" });
		// A falsy value sets the field to "", as frappe/client.py does.
		expect(normalisePayload("frappe.client.set_value", { doctype: "ToDo", name: "T1", fieldname: "status", value: 0 }).fieldname).toEqual({ status: "" });
		expect(normalisePayload("frappe.client.set_value", { doctype: "ToDo", name: "T1", fieldname: "[1, 2]" })).toBe(null);
	});

	it("refuses set_value on an underscore, server or naming key", () => {
		for (const key of ["_assign", "owner", "creation", "modified_by", "docstatus", "name", "parent"]) {
			expect(normalisePayload("frappe.client.set_value", { doctype: "ToDo", name: "T1", fieldname: { [key]: "x" } }), key).toBe(null);
		}
	});

	it("takes a write's record only from its doc, and refuses a top level that disagrees", () => {
		const doc = { doctype: "ToDo", name: "TD-1", status: "Closed" };
		expect(normalisePayload("frappe.client.save", { doc: JSON.stringify(doc) }).doc).toEqual(doc);
		expect(normalisePayload("frappe.client.save", { doc, doctype: "Note" })).toBe(null);
		expect(normalisePayload("frappe.client.save", { doc, name: "TD-2" })).toBe(null);
		expect(normalisePayload("frappe.client.insert", { doc: { status: "x" } })).toBe(null);
		expect(normalisePayload("frappe.client.save", { doc: { doctype: "ToDo" } })).toBe(null);
	});

	it("accepts a record whose name is a number", () => {
		expect(normalisePayload("frappe.client.save", { doc: { doctype: "Log", name: 42 } })).not.toBe(null);
	});

	it("refuses an insert, save or submit that is not a draft", () => {
		for (const method of ["frappe.client.insert", "frappe.client.save", "frappe.client.submit"]) {
			expect(normalisePayload(method, { doc: { doctype: "ToDo", name: "TD-1", docstatus: 1 } }), method).toBe(null);
			expect(normalisePayload(method, { doc: { doctype: "ToDo", name: "TD-1", docstatus: 0 } }), method).not.toBe(null);
		}
	});

	it("refuses parent keys on any write, and the server's keys on an insert", () => {
		for (const method of ["frappe.client.insert", "frappe.client.save", "frappe.client.submit"]) {
			for (const key of ["parent", "parenttype", "parentfield"]) {
				expect(normalisePayload(method, { doc: { doctype: "ToDo", name: "TD-1", [key]: "x" } }), `${method} ${key}`).toBe(null);
			}
		}
		for (const key of ["owner", "creation", "modified_by"]) {
			expect(normalisePayload("frappe.client.insert", { doc: { doctype: "ToDo", [key]: "x" } }), key).toBe(null);
		}
	});

	it("refuses an underscore key, except a new record's __newname and the client's own flags", () => {
		for (const key of ["_assign", "_comments", "_liked_by", "_user_tags", "_seen"]) {
			expect(normalisePayload("frappe.client.save", { doc: { doctype: "ToDo", name: "TD-1", [key]: "x" } }), key).toBe(null);
		}
		expect(normalisePayload("frappe.client.save", { doc: { doctype: "ToDo", name: "TD-1", __newname: "x" } })).toBe(null);
		expect(normalisePayload("frappe.client.insert", { doc: { doctype: "ToDo", __newname: "x", __islocal: 1 } })).not.toBe(null);
		expect(normalisePayload("frappe.client.insert", { doc: { doctype: "ToDo", items: [{ _x: 1 }] } })).toBe(null);
	});
});

describe("method names and page trust", () => {
	it("accepts only a plain dotted path as a method name", () => {
		expect(isMethodName("frappe.client.get_list")).toBe(true);
		expect(isMethodName("sales_feed")).toBe(true);
		for (const bad of ["x%2e..%2fsavedocs", "a/b", "a?cmd=x", "../x", "a..b", ".a", "a.", "", "a b"]) {
			expect(isMethodName(bad), bad).toBe(false);
		}
	});

	it("offers Allow for this page only for a plain name that could be a Server Script API method", () => {
		expect(mayTrustForPage("sales_feed")).toBe(true);
		for (const method of [
			"frappe.desk.form.save.savedocs",
			"frappe.client.insert_many",
			"erpnext.anything.at_all",
			"run_doc_method",
			"runserverobj",
			"logout",
			"x%2e..%2fsavedocs",
			"a/b",
			"a?cmd=x",
			"../x",
		]) {
			expect(mayTrustForPage(method), method).toBe(false);
		}
	});

	it("explains Allow for this page only when the site has said the method may be trusted", () => {
		expect(describePageRequest("sales_feed", {}, null, true).note).toBe(
			"Allow for this page lets this version of the page run sales_feed again without asking.",
		);
		expect(describePageRequest("sales_feed", {}, null, false).trustable).toBe(false);
		expect(describePageRequest("frappe.desk.form.save.savedocs", {}, null, true).trustable).toBe(false);
	});
});
