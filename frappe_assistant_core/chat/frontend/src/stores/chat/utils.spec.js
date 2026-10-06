import { describe, it, expect } from "vitest";
import { isFinalizedRow } from "./utils";

describe("isFinalizedRow", () => {
	it("treats an assistant row with content as finished", () => {
		expect(isFinalizedRow({ role: "assistant", content: "done" })).toBe(true);
	});

	it("treats the stream_start shell row as unfinished", () => {
		expect(isFinalizedRow({ role: "assistant", content: "", blocks: [] })).toBe(false);
		expect(isFinalizedRow({ role: "assistant", content: "", blocks: null })).toBe(false);
	});

	it("treats a terminal flag as finished even without content", () => {
		expect(isFinalizedRow({ role: "assistant", content: "", errored: 1 })).toBe(true);
		expect(isFinalizedRow({ role: "assistant", content: "", aborted: 1 })).toBe(true);
	});

	it("treats a row with blocks as finished", () => {
		expect(isFinalizedRow({ role: "assistant", content: "", blocks: [{ type: "text" }] })).toBe(
			true
		);
	});

	it("never treats a user row or a missing row as an adoptable answer", () => {
		expect(isFinalizedRow({ role: "user", content: "hi" })).toBe(false);
		expect(isFinalizedRow(null)).toBe(false);
	});
});
