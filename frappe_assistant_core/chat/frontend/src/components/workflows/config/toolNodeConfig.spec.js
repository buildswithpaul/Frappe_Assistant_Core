import { describe, it, expect } from "vitest";
import { parseArguments, argumentHints } from "./toolNodeConfig";

describe("parseArguments", () => {
	it("accepts a JSON object", () => {
		expect(parseArguments('{"report_name": "Accounts Receivable Summary"}')).toEqual({
			ok: true,
			value: { report_name: "Accounts Receivable Summary" },
		});
	});

	it("treats a blank box as no arguments", () => {
		expect(parseArguments("  ")).toEqual({ ok: true, value: {} });
	});

	it("rejects an array or a scalar", () => {
		expect(parseArguments("[1]").ok).toBe(false);
		expect(parseArguments("3").ok).toBe(false);
	});

	it("rejects broken JSON with a readable error", () => {
		const r = parseArguments("{ company: }");
		expect(r.ok).toBe(false);
		expect(r.error).toMatch(/JSON/);
	});
});

describe("argumentHints", () => {
	it("reads the tool's input schema", () => {
		const tool = {
			inputSchema: {
				properties: { report_name: {}, filters: {} },
				required: ["report_name"],
			},
		};
		expect(argumentHints(tool)).toEqual({
			names: ["report_name", "filters"],
			required: ["report_name"],
		});
	});

	it("is empty when the tool has no schema", () => {
		expect(argumentHints(null)).toEqual({ names: [], required: [] });
		expect(argumentHints({ input_schema: { properties: { a: {} } } }).names).toEqual(["a"]);
	});
});
