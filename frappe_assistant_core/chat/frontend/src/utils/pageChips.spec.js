import { describe, expect, it } from "vitest";

import { chipsForMessage, derivePageChips } from "./pageChips";

let seq = 0;
const write = (tool_name, { input = {}, result = {}, status = "success" } = {}) => ({
	type: "tool_call",
	id: `t${++seq}`,
	tool_name,
	status,
	input,
	result,
});

const created = (name, title = "Sales this month", extra = {}) =>
	write("create_document", {
		input: { doctype: "FAC Page", data: { title, slug: "sales" } },
		result: { success: true, name, doctype: "FAC Page", page_url: `/app/fac-pages/${name}` },
		...extra,
	});

const updated = (name, extra = {}) =>
	write("update_document", {
		input: { doctype: "FAC Page", name, data: { html: "<p>x</p>" } },
		result: { success: true, name, doctype: "FAC Page" },
		...extra,
	});

describe("derivePageChips", () => {
	it("gives one chip per page and counts its successful writes as the version", () => {
		const chips = derivePageChips([created("sales-a1b2c3"), updated("sales-a1b2c3"), updated("sales-a1b2c3")]);
		expect(chips).toEqual([{ name: "sales-a1b2c3", title: "Sales this month", version: 3, pending: false }]);
	});

	it("keeps pages apart, in the order they first appear", () => {
		const chips = derivePageChips([created("b-1", "B"), created("a-1", "A"), updated("b-1")]);
		expect(chips.map((c) => [c.name, c.version])).toEqual([
			["b-1", 2],
			["a-1", 1],
		]);
	});

	it("counts a prefixed tool name from a second connection", () => {
		const block = { ...created("sales-a1b2c3"), tool_name: "prod_create_document" };
		expect(derivePageChips([block])).toHaveLength(1);
	});

	it("gives no chip for a dry run", () => {
		const dry = created("sales-a1b2c3", "Sales", { input: { doctype: "FAC Page", validate_only: true } });
		expect(derivePageChips([dry])).toEqual([]);
	});

	it("gives no chip for a failed write", () => {
		const failed = write("create_document", {
			input: { doctype: "FAC Page", data: { title: "Sales" } },
			result: { success: false, error: "Missing required fields: slug" },
			status: "error",
		});
		expect(derivePageChips([failed])).toEqual([]);
	});

	it("does not count a failed update against a page that already has a chip", () => {
		const failed = updated("sales-a1b2c3", { result: { success: false, error: "nope" } });
		expect(derivePageChips([created("sales-a1b2c3"), failed])[0].version).toBe(1);
	});

	it("gives no chip for another doctype", () => {
		const other = write("create_document", {
			input: { doctype: "Server Script", data: { name: "x" } },
			result: { success: true, name: "x", doctype: "Server Script" },
		});
		expect(derivePageChips([other])).toEqual([]);
	});

	it("marks a page pending while a write to it is still running", () => {
		const running = updated("sales-a1b2c3", { status: "running", result: null });
		expect(derivePageChips([created("sales-a1b2c3"), running])).toEqual([
			{ name: "sales-a1b2c3", title: "Sales this month", version: 1, pending: true },
		]);
	});

	it("takes a new title from an update that sets one", () => {
		const retitled = write("update_document", {
			input: { doctype: "FAC Page", name: "sales-a1b2c3", data: { title: "Sales by region" } },
			result: { success: true, name: "sales-a1b2c3", doctype: "FAC Page" },
		});
		expect(derivePageChips([created("sales-a1b2c3"), retitled])[0].title).toBe("Sales by region");
	});

	it("reads a persisted result stored as MCP content parts", () => {
		const block = created("sales-a1b2c3");
		block.result = [{ text: JSON.stringify(block.result) }];
		expect(derivePageChips([block])).toHaveLength(1);
	});

	it("survives a message without blocks", () => {
		expect(derivePageChips(undefined)).toEqual([]);
	});
});

describe("chipsForMessage", () => {
	it("shows the pages this message wrote, with the conversation's version and state", () => {
		const conversation = [
			{ name: "sales-a1b2c3", title: "Sales by region", version: 3, pending: true },
			{ name: "other-1", title: "Other", version: 1, pending: false },
		];
		expect(chipsForMessage([updated("sales-a1b2c3")], conversation)).toEqual([conversation[0]]);
	});
});

describe("derivePageChips with a cancelled write", () => {
	it("does not count it", () => {
		const cancelled = updated("sales-a1b2c3", { status: "cancelled", result: { message: "cancelled" } });
		expect(derivePageChips([created("sales-a1b2c3"), cancelled])[0].version).toBe(1);
	});
});
