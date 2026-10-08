import { describe, it, expect } from "vitest";
import { isPausedTurn, isStoppedTurn, turnWaitingOn } from "./turnState";

const PENDING_CARD = { type: "interaction", id: "tu-1", status: "pending" };

describe("isPausedTurn", () => {
	it("is true while an interaction card waits for the user", () => {
		expect(isPausedTurn([{ type: "tool_call", status: "running" }, PENDING_CARD])).toBe(true);
	});

	// recordInteractionDecision marks the card decided before the resume goes
	// out; from then on the turn waits on the resume, not on the user.
	it("is false once every pending card carries the user's decision", () => {
		expect(isPausedTurn([{ ...PENDING_CARD, decision: { resolution: "approved" } }])).toBe(false);
	});

	it("is false once every card is resolved, and for a turn without blocks", () => {
		expect(isPausedTurn([{ ...PENDING_CARD, status: "approved" }])).toBe(false);
		expect(isPausedTurn(undefined)).toBe(false);
	});
});

describe("isStoppedTurn", () => {
	it("is true for an aborted turn", () => {
		expect(isStoppedTurn({ aborted: 1, blocks: [] })).toBe(true);
		expect(isStoppedTurn({ aborted: 0, blocks: [] })).toBe(false);
	});

	// handleStreamAborted keeps the local blocks when the stream_aborted event
	// carries no snapshot, so an aborted message can still hold a pending card.
	it("is false while a card still waits, even on an aborted message", () => {
		expect(isStoppedTurn({ aborted: true, blocks: [PENDING_CARD] })).toBe(false);
	});
});

describe("turnWaitingOn", () => {
	it("names the kind of card the turn waits on", () => {
		expect(turnWaitingOn([PENDING_CARD], false)).toBe("approval");
		expect(turnWaitingOn([{ ...PENDING_CARD, interactionType: "question" }], false)).toBe("question");
	});

	// submitInterruptDecision keeps isSubmittingInterrupts set until the
	// resume stream's first event; the answered card no longer waits.
	it("waits on the resume once the card is answered", () => {
		expect(turnWaitingOn([{ ...PENDING_CARD, status: "approved" }], true)).toBe("resume");
	});

	it("waits on nothing otherwise", () => {
		expect(turnWaitingOn([{ ...PENDING_CARD, status: "approved" }], false)).toBe("");
	});
});
