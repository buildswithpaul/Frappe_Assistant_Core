import { describe, it, expect } from "vitest";
import { processingSummary } from "./processingSummary";

const runningDelegate = {
	type: "tool_call",
	tool_name: "delegate",
	isInternal: true,
	status: "running",
};

describe("processingSummary — live", () => {
	it("shows clear activity while a delegate subtask runs", () => {
		expect(processingSummary([runningDelegate], true)).toBe("Delegating subtask…");
	});

	it("falls back to Preparing... for other internal tools", () => {
		const block = { type: "tool_call", tool_name: "get_skill", isInternal: true, status: "running" };
		expect(processingSummary([block], true)).toBe("Preparing...");
	});

	it("names external tools while running", () => {
		const block = { type: "tool_call", tool_name: "search_link", status: "running" };
		expect(processingSummary([block], true)).toBe("Running Search Link...");
	});
});

describe("processingSummary — completed", () => {
	it("reads a finished delegate as deliberate activity", () => {
		const block = { ...runningDelegate, status: "success" };
		expect(processingSummary([block], false)).toBe("Delegated 1 subtask");
	});

	it("pluralizes multiple delegated subtasks", () => {
		const blocks = [
			{ ...runningDelegate, status: "success" },
			{ ...runningDelegate, status: "success" },
		];
		expect(processingSummary(blocks, false)).toBe("Delegated 2 subtasks");
	});

	it("surfaces delegate failures", () => {
		const blocks = [
			{ ...runningDelegate, status: "success" },
			{ ...runningDelegate, status: "error" },
		];
		expect(processingSummary(blocks, false)).toBe("Delegated 2 subtasks (1 failed)");
	});

	it("lets the external Used... line win when external tools also ran", () => {
		const blocks = [
			{ ...runningDelegate, status: "success" },
			{ type: "tool_call", tool_name: "search_link", isInternal: false, status: "success" },
		];
		expect(processingSummary(blocks, false)).toBe("Used Search Link");
	});

	it("keeps get_skill phrasing untouched", () => {
		const block = { type: "tool_call", tool_name: "get_skill", isInternal: true, status: "success" };
		expect(processingSummary([block], false)).toBe("Loaded skill documentation");
	});
});

describe("processingSummary — thinking", () => {
	const thinking = { type: "thinking", content: "Working it out…" };
	const getSkill = {
		type: "tool_call",
		tool_name: "get_skill",
		isInternal: true,
		status: "success",
	};

	it("does not let one internal get_skill hide that the model thought", () => {
		// The live gpt-5.x shape with Thinking on: thinking, an internal
		// get_skill, more thinking, then text. This read "Loaded skill
		// documentation", so the toggle's only visible payoff was invisible
		// unless the card was expanded.
		const blocks = [thinking, getSkill, thinking, { type: "text", content: "Done." }];
		expect(processingSummary(blocks, false)).toBe("Thought about the request");
	});

	it("outranks the generic internal-prep label too", () => {
		const blocks = [
			thinking,
			{ type: "tool_call", tool_name: "recall", isInternal: true, status: "success" },
			getSkill,
		];
		expect(processingSummary(blocks, false)).toBe("Thought about the request");
	});

	it("still lets external tools win — they are the substantive work", () => {
		const blocks = [
			thinking,
			{ type: "tool_call", tool_name: "search_link", isInternal: false, status: "success" },
		];
		expect(processingSummary(blocks, false)).toBe("Used Search Link");
	});

	it("still lets delegation win — it names work worth seeing", () => {
		const blocks = [thinking, { ...runningDelegate, status: "success" }];
		expect(processingSummary(blocks, false)).toBe("Delegated 1 subtask");
	});

	it("leaves the internal-prep labels alone when no thinking happened", () => {
		expect(processingSummary([getSkill], false)).toBe("Loaded skill documentation");
	});
});
