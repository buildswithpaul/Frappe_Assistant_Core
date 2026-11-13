import { describe, expect, it } from "vitest";

import { makeBlocks } from "./pageBlocks";
import { fakeFrappe } from "./__tests__/pageBlocksFake";

describe("canWrite", () => {
	it("answers whether the viewer may write the record", async () => {
		const f = fakeFrappe({ answers: { "frappe.client.has_permission": { has_permission: true } } });
		expect(await makeBlocks(f).canWrite("ToDo", "T-1")).toBe(true);
		expect(f.calls[0]).toMatchObject({
			method: "frappe.client.has_permission",
			type: "GET",
			args: { doctype: "ToDo", docname: "T-1", perm_type: "write" },
		});
	});

	it("answers false when the viewer may not", async () => {
		const f = fakeFrappe({ answers: { "frappe.client.has_permission": { has_permission: false } } });
		expect(await makeBlocks(f).canWrite("ToDo", "T-1")).toBe(false);
	});

	it("answers false when the check itself fails", async () => {
		const f = fakeFrappe({ answers: { "frappe.client.has_permission": new Error("offline") } });
		expect(await makeBlocks(f).canWrite("ToDo", "T-1")).toBe(false);
	});
});

describe("updated", () => {
	it("says who changed the record last and when", () => {
		const text = makeBlocks(fakeFrappe()).updated({ modified_by: "avery@example.com", modified: "2026-11-13 10:00:00" });
		expect(text).toBe("Updated by avery@example.com · 13-11-2026");
	});

	it("leaves out what the record does not carry", () => {
		const blocks = makeBlocks(fakeFrappe());
		expect(blocks.updated({ modified_by: "avery@example.com" })).toBe("Updated by avery@example.com");
		expect(blocks.updated({})).toBe("");
	});
});

