import { describe, it, expect } from "vitest";
import { buildTimelineRows, toolDurationMs } from "./useActivityTimeline";

describe("buildTimelineRows", () => {
	it("skips internal tools and thinking blocks", () => {
		const rows = buildTimelineRows([
			{ type: "thinking", id: "t1" },
			{ type: "tool_call", id: "x1", tool_name: "get_skill", isInternal: true, status: "success" },
			{ type: "tool_call", id: "x2", tool_name: "search_link", input: { txt: "Promantia" }, status: "success" },
		]);
		expect(rows).toHaveLength(1);
		expect(rows[0].id).toBe("x2");
	});

	it("phrases known tools in plain language with the target", () => {
		const [row] = buildTimelineRows([
			{ type: "tool_call", id: "a", tool_name: "search_link", input: { txt: "Promantia" }, status: "success" },
		]);
		expect(row.label).toBe("Searched records → Promantia");
		expect(row.hasTarget).toBe(true);
		expect(row.status).toBe("success");
	});

	it("reads doctype targets for get_doctype_info", () => {
		const [row] = buildTimelineRows([
			{ type: "tool_call", id: "b", tool_name: "get_doctype_info", input: { doctype: "Sales Order" }, status: "success" },
		]);
		expect(row.label).toBe("Read doctype → Sales Order");
	});

	it("falls back to a humanized name for unknown tools and no target", () => {
		const [row] = buildTimelineRows([
			{ type: "tool_call", id: "c", tool_name: "weird_custom_tool", input: {}, status: "running" },
		]);
		expect(row.label).toBe("Weird Custom Tool");
		expect(row.hasTarget).toBe(false);
		expect(row.status).toBe("running");
	});

	it("preserves the raw block for the I/O drawer", () => {
		const block = { type: "tool_call", id: "d", tool_name: "list_documents", input: { doctype: "Item" }, result: [{}], status: "success" };
		const [row] = buildTimelineRows([block]);
		expect(row.block).toBe(block);
	});
});

describe("toolDurationMs", () => {
	it("prefers server duration_ms", () => {
		expect(toolDurationMs({ duration_ms: 840, startTime: "2026-07-20T09:00:00Z", endTime: "2026-07-20T09:00:05Z" })).toBe(840);
	});
	it("falls back to endTime - startTime", () => {
		expect(toolDurationMs({ startTime: "2026-07-20T09:00:00.000Z", endTime: "2026-07-20T09:00:02.500Z" })).toBe(2500);
	});
	it("is null while running or on bad data", () => {
		expect(toolDurationMs({ startTime: "2026-07-20T09:00:00Z", endTime: null })).toBe(null);
		expect(toolDurationMs({ startTime: "nope", endTime: "worse" })).toBe(null);
	});
});

// A turn persisted before `delegate` joined the server's INTERNAL_TOOLS keeps
// isInternal false on its delegate block, so after a reload the rail drew a
// "Delegate" row next to the plan that already shows the delegated work.
describe("buildTimelineRows on a persisted delegate block", () => {
	it("skips a delegate block whose isInternal flag was persisted false", () => {
		const rows = buildTimelineRows([
			{ type: "tool_call", id: "d1", tool_name: "delegate", isInternal: false, status: "running" },
		]);
		expect(rows).toEqual([]);
	});
});

describe("buildTimelineRows for customisation writes", () => {
	const create = (extra) => ({
		type: "tool_call",
		id: "c",
		tool_name: "create_document",
		input: { doctype: "Server Script" },
		...extra,
	});

	it("successful create reads Created with name", () => {
		const [row] = buildTimelineRows([create({ status: "success", result: { success: true, name: "Discount limit" } })]);
		expect(row.label).toBe("Created Server Script → Discount limit");
		expect(row.labelPrefix).toBe("Created Server Script → ");
		expect(row.target).toBe("Discount limit");
	});

	it("reads the name from a JSON string result and tolerates truncated ones", () => {
		const [named] = buildTimelineRows([create({ status: "success", result: '{"name":"Discount limit"}' })]);
		expect(named.label).toBe("Created Server Script → Discount limit");
		const [cut] = buildTimelineRows([create({ status: "success", result: '{"name":"Disc' })]);
		expect(cut.label).toBe("Created Server Script");
		expect(cut.hasTarget).toBe(false);
	});

	it("reads the name from the stored content-parts result", () => {
		const result = [{ text: JSON.stringify({ success: true, name: "Discount limit" }) }];
		const [row] = buildTimelineRows([create({ status: "success", result })]);
		expect(row.label).toBe("Created Server Script → Discount limit");
	});

	it("labels a validate_only create as Checked, not Created", () => {
		const input = { doctype: "Server Script", validate_only: true, data: {} };
		const result = [{ text: JSON.stringify({ success: true, validation_passed: true, doctype: "Server Script" }) }];
		const [row] = buildTimelineRows([create({ status: "success", input, result })]);
		expect(row.label).toBe("Checked Server Script");
		expect(row.hasTarget).toBe(false);
	});

	it("labels a validation result as Checked even when the input flag is missing", () => {
		const [row] = buildTimelineRows([create({ status: "success", result: { success: true, validation_passed: true } })]);
		expect(row.label).toBe("Checked Server Script");
	});

	it("a real create with validate_only false still reads Created", () => {
		const input = { doctype: "Server Script", validate_only: false };
		const [row] = buildTimelineRows([create({ status: "success", input, result: { success: true, name: "X" } })]);
		expect(row.label).toBe("Created Server Script → X");
	});

	it("pending and failed create keep the prepared wording", () => {
		const [running] = buildTimelineRows([create({ status: "running", result: null })]);
		expect(running.label).toBe("Prepared new record → Server Script");
		const [failed] = buildTimelineRows([create({ status: "error", result: { success: false, error: "Nope" } })]);
		expect(failed.label).toBe("Prepared new record → Server Script");
	});

	it("update and document actions read in the past tense", () => {
		const update = { type: "tool_call", id: "u", tool_name: "update_document", status: "success", input: { doctype: "Client Script", name: "CS-1" }, result: { name: "CS-1" } };
		expect(buildTimelineRows([update])[0].label).toBe("Updated Client Script → CS-1");
		const action = (a) => ({ type: "tool_call", id: a, tool_name: "document_action", status: "success", input: { doctype: "Quotation", name: "Q-1", action: a }, result: { success: true } });
		expect(buildTimelineRows([action("submit")])[0].label).toBe("Submitted Quotation → Q-1");
		expect(buildTimelineRows([action("cancel")])[0].label).toBe("Cancelled Quotation → Q-1");
		expect(buildTimelineRows([action("amend")])[0].label).toBe("Amended Quotation → Q-1");
	});

	it("failed step shows the plain reason", () => {
		const [row] = buildTimelineRows([create({ status: "error", result: { success: false, error: "Server scripts are disabled. Ask an admin." } })]);
		expect(row.reason).toBe("Server scripts are disabled.");
		const [ok] = buildTimelineRows([create({ status: "success", result: { name: "X" } })]);
		expect(ok.reason).toBe("");
	});
});

describe("buildTimelineRows for prefixed tool names", () => {
	it("reads a second connection's create as Created", () => {
		const [row] = buildTimelineRows([
			{ type: "tool_call", id: "p", tool_name: "prod_create_document", status: "success", input: { doctype: "Role" }, result: { name: "Auditor" } },
		]);
		expect(row.label).toBe("Created Role → Auditor");
	});
});

describe("buildTimelineRows status of a failure payload", () => {
	it("marks a step whose result says success false as an error", () => {
		const [row] = buildTimelineRows([
			{ type: "tool_call", id: "f", tool_name: "create_document", status: "success", input: { doctype: "Role" }, result: { success: false, error: "Name taken" } },
		]);
		expect(row.status).toBe("error");
		expect(row.reason).toBe("Name taken");
	});
});

describe("toolRowFrom open link", () => {
	const write = (result, extra = {}) => ({
		type: "tool_call",
		id: "w1",
		tool_name: "create_document",
		status: "success",
		input: { doctype: "Custom Field", data: { dt: "Customer" } },
		result,
		...extra,
	});

	it("carries the form to open when a successful write names one", () => {
		const [row] = buildTimelineRows([write({ name: "Customer-po", applies_to: { doctype: "Customer", url: "/desk/customer/new" } })]);
		expect(row.appliesTo).toEqual({ doctype: "Customer", url: "/desk/customer/new" });
	});

	it("has no link without applies_to, with an unsafe url, or on a failed write", () => {
		expect(buildTimelineRows([write({ name: "x" })])[0].appliesTo).toBeNull();
		expect(buildTimelineRows([write({ applies_to: { doctype: "Customer", url: "javascript:alert(1)" } })])[0].appliesTo).toBeNull();
		const failed = write({ success: false, applies_to: { doctype: "Customer", url: "/desk/customer/new" } });
		expect(buildTimelineRows([failed])[0].appliesTo).toBeNull();
	});
});
