import { describe, it, expect } from "vitest";
import { answeredCardIds, carryCardDecisions, isFinalizedRow, resumeHasSettled } from "./utils";

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

describe("resumeHasSettled", () => {
	const row = (blocks, extra = {}) => ({ role: "assistant", message_id: "m-1", blocks, ...extra });
	const card = (id, status) => ({ type: "interaction", id, status });

	it("is unsettled while an answered card is still pending on the row", () => {
		expect(resumeHasSettled(row([card("call_1", "pending")]), new Set(["call_1"]))).toBe(false);
	});

	it("is settled once every answered card has moved on", () => {
		expect(resumeHasSettled(row([card("call_1", "approved")]), new Set(["call_1"]))).toBe(true);
		expect(resumeHasSettled(row([card("call_1", "pending")], { errored: 1 }), new Set(["call_1"]))).toBe(true);
	});

	// No answered card means there is nothing to judge the row by.
	it("is unsettled without any answered card", () => {
		expect(resumeHasSettled(row([card("call_1", "approved")]), new Set())).toBe(false);
	});

	// handleApprovalRequired mints `interaction-N` when approval_required carries
	// no tool_id, and the server row knows that card by another id.
	it("is unsettled when an answered card is not on the row", () => {
		expect(resumeHasSettled(row([card("call_1", "approved")]), new Set(["interaction_1"]))).toBe(false);
	});
});

describe("answeredCardIds", () => {
	// recordInteractionDecision sets `decision` at once; the status flips only
	// after the resume_interrupt call returns.
	it("counts a decided card whose status has not flipped yet", () => {
		const msg = { blocks: [{ type: "interaction", id: "call_1", status: "pending", decision: {} }] };
		expect(answeredCardIds(msg)).toEqual(new Set(["call_1"]));
	});
});

describe("carryCardDecisions", () => {
	const decided = {
		type: "interaction",
		id: "call_1",
		status: "pending",
		interrupts: [{ id: "int1" }],
		decision: { resolution: "approved" },
	};
	const snapshotCard = (interrupts) => ({ type: "interaction", id: "call_1", status: "pending", interrupts });

	it("carries a decision onto the same pending card", () => {
		const [card] = carryCardDecisions([decided], [snapshotCard([{ id: "int1" }])]);
		expect(card.decision).toEqual({ resolution: "approved" });
	});

	// A card id is the gated tool's id, which a re-interrupt of the same tool can
	// reuse; the interrupt ids are what the decision answers.
	it("does not carry a decision onto a card asking about other interrupts", () => {
		const [card] = carryCardDecisions([decided], [snapshotCard([{ id: "int2" }])]);
		expect(card.decision).toBeUndefined();
	});
});
