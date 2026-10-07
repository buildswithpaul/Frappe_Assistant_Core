import { describe, it, expect } from "vitest";
import { isPausedTurn, isStoppedTurn } from "./turnState";

const PENDING_CARD = { type: "interaction", id: "tu-1", status: "pending" };

describe("isPausedTurn", () => {
	it("is true while an interaction card waits for the user", () => {
		expect(isPausedTurn([{ type: "tool_call", status: "running" }, PENDING_CARD])).toBe(true);
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
