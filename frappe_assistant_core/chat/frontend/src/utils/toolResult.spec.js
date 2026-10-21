import { describe, it, expect } from "vitest";
import { toolResult, safeUrl, failureReason, toolFailed } from "./toolResult";

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

describe("toolResult unwraps tool-result content parts", () => {
	const payload = { success: true, name: "SS-1", url: "/desk/server-script/SS-1", applies_to: { doctype: "Lead" } };
	const json = JSON.stringify(payload);

	it("reads Strands text parts, as the runtime streams and stores them", () => {
		expect(toolResult({ result: [{ text: json }] })).toEqual(payload);
	});

	it("reads MCP text parts and skips non-text parts", () => {
		expect(toolResult({ result: [{ type: "text", text: json }, { type: "image", data: "xx" }] })).toEqual(payload);
	});

	it("reads a json part", () => {
		expect(toolResult({ result: [{ json: payload }] })).toEqual(payload);
	});

	it("reads an MCP result wrapper with content parts", () => {
		expect(toolResult({ result: { content: [{ type: "text", text: json }], isError: false } })).toEqual(payload);
	});

	it("prefers structuredContent over the text parts", () => {
		const wrapper = { content: [{ text: '{"name":"from text"}' }], structuredContent: payload };
		expect(toolResult({ result: wrapper })).toEqual(payload);
	});

	it("reads parts that arrive as a JSON string", () => {
		expect(toolResult({ result: JSON.stringify([{ text: json }]) })).toEqual(payload);
	});

	it("treats parts with truncated or plain text as having no fields", () => {
		expect(toolResult({ result: [{ text: '{"name":"SS' }] })).toEqual({});
		expect(toolResult({ result: [{ text: "Done." }] })).toEqual({});
		expect(toolResult({ result: [{ text: json.slice(0, 20) }] })).toEqual({});
	});

	it("keeps a plain result that happens to have a content field", () => {
		expect(toolResult({ result: { name: "N", content: "hello" } })).toEqual({ name: "N", content: "hello" });
	});

	it("flags an MCP error wrapper as failed", () => {
		const result = { content: [{ type: "text", text: '{"error":"Nope. More."}' }], isError: true };
		expect(toolFailed({ status: "success", result })).toBe(true);
		expect(failureReason({ status: "success", result })).toBe("Nope.");
	});
});

describe("safeUrl", () => {
	it("accepts site paths and web URLs only", () => {
		expect(safeUrl("/desk/server-script/X")).toBe("/desk/server-script/X");
		expect(safeUrl("https://a.example/desk/x")).toBe("https://a.example/desk/x");
		for (const bad of ["javascript:alert(1)", "//evil.example", "/\\evil.example", "", null, 5]) {
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
