import { describe, it, expect } from "vitest";
import { shouldShowProcessingIndicator } from "@/components/chat/indicatorVisibility";

describe("shouldShowProcessingIndicator", () => {
	it("hidden when not streaming", () =>
		expect(shouldShowProcessingIndicator(false, [{ type: "plan" }])).toBe(false));
	it("shown before any block arrives", () =>
		expect(shouldShowProcessingIndicator(true, [])).toBe(true));
	it("shown when last block is a plan (task rail turn)", () =>
		expect(shouldShowProcessingIndicator(true, [{ type: "plan" }])).toBe(true));
	it("shown when last block is sources (RAG TTFT window)", () =>
		expect(shouldShowProcessingIndicator(true, [{ type: "sources" }])).toBe(true));
	it("shown after a resolved interaction (HITL resume)", () =>
		expect(shouldShowProcessingIndicator(true, [{ type: "interaction", status: "approved" }])).toBe(true));
	it("hidden while waiting on a pending interaction", () =>
		expect(shouldShowProcessingIndicator(true, [{ type: "interaction", status: "pending" }])).toBe(false));
	it("hidden while a tool card shows its own spinner", () =>
		expect(shouldShowProcessingIndicator(true, [{ type: "tool_call", status: "running" }])).toBe(false));
	it("shown after a tool completes", () =>
		expect(shouldShowProcessingIndicator(true, [{ type: "tool_call", status: "completed" }])).toBe(true));
	it("hidden while text streams (dots own it)", () =>
		expect(shouldShowProcessingIndicator(true, [{ type: "text" }])).toBe(false));
	it("hidden while a thinking block streams", () =>
		expect(shouldShowProcessingIndicator(true, [{ type: "thinking", isStreaming: true }])).toBe(false));
	it("shown after thinking completes", () =>
		expect(shouldShowProcessingIndicator(true, [{ type: "thinking", isStreaming: false }])).toBe(true));
});
