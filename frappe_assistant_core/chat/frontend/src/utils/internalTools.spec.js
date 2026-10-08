import { describe, it, expect } from "vitest";
import { INTERNAL_TOOLS, isInternalTool } from "./internalTools";
import { INTERNAL_TOOLS as STREAM_INTERNAL_TOOLS } from "@/stores/chat/blockHandlers";
import { processingSummary } from "@/components/chat/processingSummary";

describe("isInternalTool", () => {
	it("trusts the block's flag", () => {
		expect(isInternalTool({ tool_name: "anything", isInternal: true })).toBe(true);
	});

	// Rows persisted while the server list lacked `delegate` carry isInternal false.
	it("also decides by name, for blocks persisted with a stale flag", () => {
		expect(isInternalTool({ tool_name: "delegate", isInternal: false })).toBe(true);
		expect(isInternalTool({ tool_name: "list_documents", isInternal: false })).toBe(false);
	});

	it("is the list the stream handlers flag blocks with", () => {
		expect(STREAM_INTERNAL_TOOLS).toBe(INTERNAL_TOOLS);
	});

	it("keeps a persisted delegate block out of the finished card's tool count", () => {
		const blocks = [
			{ type: "tool_call", id: "d1", tool_name: "delegate", isInternal: false, status: "success" },
			{ type: "tool_call", id: "t1", tool_name: "list_documents", isInternal: false, status: "success" },
		];
		expect(processingSummary(blocks, false)).toBe(processingSummary([blocks[1]], false));
	});
});
