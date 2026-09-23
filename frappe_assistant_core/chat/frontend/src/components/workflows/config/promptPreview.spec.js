import { describe, it, expect } from "vitest";
import {
	substituteVariables,
	buildToolDirectiveBlock,
	estimateTokens,
	buildResolvedPrompt,
} from "@/components/workflows/config/promptPreview";
import { resolutionIndex } from "@/components/workflows/config/toolDirectives";

describe("substituteVariables", () => {
	it("substitutes the backend-correct {{name}} form", () => {
		const { text } = substituteVariables("Report for {{company}}", { company: "Acme" });
		expect(text).toBe("Report for Acme");
	});

	it("tolerates inner whitespace", () => {
		expect(substituteVariables("{{ company }}", { company: "Acme" }).text).toBe("Acme");
	});

	it("leaves an unknown placeholder in place and names it", () => {
		const { text, unresolved } = substituteVariables("Hi {{missing}}", {});
		expect(text).toBe("Hi {{missing}}");
		expect(unresolved).toEqual(["missing"]);
	});
});

describe("buildToolDirectiveBlock", () => {
	it("is empty when the node declares no tools", () => {
		expect(buildToolDirectiveBlock([], new Map())).toBe("");
	});

	it("lists primary tools under Required Tools with the prefixed name", () => {
		const resolution = resolutionIndex([
			{
				tool_name: "list_documents",
				status: "resolved",
				prefixed_name: "Main Frappe Site:list_documents",
			},
		]);
		const block = buildToolDirectiveBlock(
			[{ tool_name: "list_documents", priority: "primary" }],
			resolution
		);
		expect(block).toContain("## Required Tools");
		expect(block).toContain("- `Main Frappe Site:list_documents`");
	});

	it("separates secondary tools", () => {
		const block = buildToolDirectiveBlock(
			[{ tool_name: "web_search", priority: "secondary" }],
			new Map()
		);
		expect(block).toContain("## Additional Tools");
		expect(block).not.toContain("## Required Tools");
	});

	it("surfaces the unavailable-tools note the engine would append", () => {
		const resolution = resolutionIndex([{ tool_name: "ghost_tool", status: "missing" }]);
		const block = buildToolDirectiveBlock([{ tool_name: "ghost_tool" }], resolution);
		expect(block).toContain("Note: These tools are not available: ghost_tool");
	});

	it("does not pre-judge a tool with no resolution data yet", () => {
		const block = buildToolDirectiveBlock([{ tool_name: "list_documents" }], new Map());
		expect(block).toContain("## Required Tools");
		expect(block).not.toContain("not available");
	});
});

describe("estimateTokens", () => {
	it("is zero for an empty prompt", () => {
		expect(estimateTokens("")).toBe(0);
		expect(estimateTokens("   ")).toBe(0);
	});

	it("scales with length", () => {
		expect(estimateTokens("a".repeat(400))).toBe(100);
	});
});

describe("buildResolvedPrompt", () => {
	it("shows both halves — substituted prompt and appended tool block", () => {
		const resolution = resolutionIndex([
			{
				tool_name: "list_documents",
				status: "resolved",
				prefixed_name: "Main Frappe Site:list_documents",
			},
		]);
		const result = buildResolvedPrompt({
			systemPrompt: "Summarize invoices for {{company}}.",
			variables: { company: "Acme" },
			directives: [{ tool_name: "list_documents", priority: "primary" }],
			resolution,
		});
		expect(result.text).toContain("Summarize invoices for Acme.");
		expect(result.text).toContain("- `Main Frappe Site:list_documents`");
		expect(result.tokens).toBeGreaterThan(0);
	});

	it("reports missing tools and unresolved variables", () => {
		const resolution = resolutionIndex([{ tool_name: "ghost_tool", status: "missing" }]);
		const result = buildResolvedPrompt({
			systemPrompt: "Use {{nope}}",
			directives: [{ tool_name: "ghost_tool" }],
			resolution,
		});
		expect(result.unresolvedVariables).toEqual(["nope"]);
		expect(result.missingTools).toEqual(["ghost_tool"]);
	});
});
