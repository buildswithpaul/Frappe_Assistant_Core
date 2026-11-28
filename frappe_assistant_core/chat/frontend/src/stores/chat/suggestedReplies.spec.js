import { describe, it, expect } from "vitest";
import { repliesToShow, suggestedReplies, SUGGESTED_REPLIES_BLOCK } from "./suggestedReplies";

const reply = (replies) => ({
	role: "assistant",
	blocks: [{ type: "text", content: "Shall I submit it?" }, { type: SUGGESTED_REPLIES_BLOCK, replies }],
});

describe("suggested replies", () => {
	it("cleans the answers: single line, no repeats, three at most", () => {
		expect(suggestedReplies(["Yes,\n go ahead", "yes, go ahead", "x".repeat(81), "No", "Later", "Fourth"])).toEqual([
			"Yes, go ahead",
			"No",
			"Later",
		]);
		expect(suggestedReplies("Yes")).toEqual([]);
		expect(suggestedReplies([null, 3, "  "])).toEqual([]);
	});

	it("shows them only under the latest reply, once it has finished", () => {
		const message = reply(["Yes, submit it", "Stop here"]);

		expect(repliesToShow(message, { isLatest: true, isStreaming: false })).toEqual(["Yes, submit it", "Stop here"]);
		expect(repliesToShow(message, { isLatest: false, isStreaming: false })).toEqual([]);
		expect(repliesToShow(message, { isLatest: true, isStreaming: true })).toEqual([]);
		expect(repliesToShow({ ...message, role: "user" }, { isLatest: true, isStreaming: false })).toEqual([]);
		expect(repliesToShow({ role: "assistant", blocks: [] }, { isLatest: true, isStreaming: false })).toEqual([]);
	});
});
