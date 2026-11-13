import { describe, expect, it } from "vitest";

import { makeBlocks } from "./pageBlocks";

// A page's frappe as the blocks use it: call with {method, type, args} answering {message},
// db.get_doc, and datetime.str_to_user. Desk's frappe and the chat's stand-in both offer these.
function fakeFrappe({ answers = {}, docs = [] } = {}) {
	const calls = [];
	const reads = [...docs];
	return {
		calls,
		call(opts) {
			calls.push(opts);
			const answer = answers[opts.method];
			if (answer instanceof Error) return Promise.reject(answer);
			return Promise.resolve({ message: typeof answer === "function" ? answer(opts.args) : answer });
		},
		db: {
			get_doc: () => Promise.resolve(structuredClone(reads.length > 1 ? reads.shift() : reads[0])),
		},
		datetime: { str_to_user: (value) => (value ? "13-11-2026" : "") },
	};
}

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

export { fakeFrappe };
