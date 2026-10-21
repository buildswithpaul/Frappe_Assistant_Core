import { describe, it, expect } from "vitest";
import { toolResult, safeUrl, failureReason } from "./toolResult";

describe("toolResult", () => {
	it("returns an object result as is", () => {
		expect(toolResult({ result: { name: "A" } })).toEqual({ name: "A" });
	});

	it("parses a JSON string result", () => {
		expect(toolResult({ result: '{"name":"A","url":"/desk/x"}' })).toEqual({ name: "A", url: "/desk/x" });
	});

	it("treats truncated JSON, plain text, arrays and null as having no fields", () => {
		for (const result of ['{"name":"A","ur', "ok", [{}], null, undefined, 5]) {
			expect(toolResult({ result })).toEqual({});
		}
	});
});

describe("safeUrl", () => {
	it("accepts site paths and web URLs only", () => {
		expect(safeUrl("/desk/server-script/X")).toBe("/desk/server-script/X");
		expect(safeUrl("https://a.example/desk/x")).toBe("https://a.example/desk/x");
		for (const bad of ["javascript:alert(1)", "//evil.example", "", null, 5]) {
			expect(safeUrl(bad)).toBe(null);
		}
	});
});

describe("failureReason", () => {
	const failed = (result) => ({ status: "error", result });

	it("uses error, then message, trimmed to the first sentence", () => {
		expect(failureReason(failed({ error: "Server scripts are disabled. Ask an admin to enable them." }))).toBe(
			"Server scripts are disabled.",
		);
		expect(failureReason(failed({ message: "Not permitted" }))).toBe("Not permitted");
	});

	it("caps long reasons", () => {
		const reason = failureReason(failed({ error: "x".repeat(300) }));
		expect(reason.length).toBe(140);
		expect(reason.endsWith("…")).toBe(true);
	});

	it("never shows a traceback and says nothing for a successful step", () => {
		expect(failureReason(failed({ error: "Traceback (most recent call last):\n  File x" }))).toBe("");
		expect(failureReason({ status: "success", result: { message: "Done" } })).toBe("");
	});

	it("also reads a failure payload on a step marked successful", () => {
		expect(failureReason({ status: "success", result: { success: false, error: "Name already exists" } })).toBe(
			"Name already exists",
		);
	});
});
