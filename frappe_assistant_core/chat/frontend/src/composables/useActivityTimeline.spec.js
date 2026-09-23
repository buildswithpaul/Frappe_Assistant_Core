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
