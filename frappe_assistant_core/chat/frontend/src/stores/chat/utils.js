/**
 * Shared utilities for chat store modules.
 */

let blockIdCounter = 0;

export function generateBlockId(prefix = "block") {
	return `${prefix}_${Date.now()}_${++blockIdCounter}`;
}

// Whether a persisted assistant row represents a finished turn. Streaming
// persists an empty shell row at stream_start and backfills it on completion,
// so "has content, blocks, or a terminal flag" is what separates a turn that
// landed from one still in flight.
export function isFinalizedRow(msg) {
	if (!msg || msg.role !== "assistant") return false;
	if (msg.errored || msg.aborted) return true;
	return Boolean(msg.content) || (Array.isArray(msg.blocks) && msg.blocks.length > 0);
}

// Carry the user's card decisions from the blocks on screen onto a server
// snapshot of the same turn. A paused stream can end after the user decided
// (a helper kept it open), and its snapshot still holds those cards pending.
export function carryCardDecisions(localBlocks, snapshotBlocks) {
	const decided = new Map(
		(Array.isArray(localBlocks) ? localBlocks : [])
			.filter((b) => b?.type === "interaction" && b.decision)
			.map((b) => [b.id, b])
	);
	if (!decided.size || !Array.isArray(snapshotBlocks)) return snapshotBlocks;
	return snapshotBlocks.map((b) => {
		const local = b?.type === "interaction" && b.status === "pending" && decided.get(b.id);
		if (!local || !sameInterrupts(local, b)) return b;
		const { decision, status, userResponse, endTime, isExpanded } = local;
		return { ...b, decision, status, userResponse, endTime, isExpanded };
	});
}

// A decision answers specific interrupts; a card id alone (the gated tool's id)
// can come back on a later pause.
function sameInterrupts(a, b) {
	const ids = (card) => (card.interrupts || []).map((i) => i?.id).sort().join("\n");
	return ids(a) === ids(b);
}

// The ids of the cards the user answered on a turn. recordInteractionDecision
// sets `decision` at once, and only a fully decided batch is resumed; the
// status flips later, once the resume_interrupt call returns.
export function answeredCardIds(msg) {
	const blocks = Array.isArray(msg?.blocks) ? msg.blocks : [];
	return new Set(blocks.filter((b) => b?.type === "interaction" && b.decision).map((b) => b.id));
}

// Whether a paused turn's server row shows the outcome of the resume that
// answered `answeredIds`. The relay persists nothing mid-resume, so until the
// resume ends those cards are still pending on the row. Once every one of them
// has moved on, the row holds an outcome: an answer, a new pause on a further
// card, or the cards written `expired` because the pause was already gone.
// Without an answered card, or with one the row does not know (a client-minted
// `interaction-N` id), there is nothing to judge the row by: unsettled.
export function resumeHasSettled(row, answeredIds) {
	if (!row) return false;
	if (row.errored || row.aborted) return true;
	if (!answeredIds?.size) return false;
	const cards = new Map(
		(Array.isArray(row.blocks) ? row.blocks : [])
			.filter((b) => b?.type === "interaction")
			.map((b) => [b.id, b])
	);
	return [...answeredIds].every((id) => cards.has(id) && cards.get(id).status !== "pending");
}

// `messages[length-1]` stops being "the active turn" the instant a non-turn
// entry lands on the tail. Two do: compose-while-streaming bubbles (queued
// while the assistant message keeps streaming) and `role: "divider"` markers
// pushed by handleContextSummarized — AR emits context_summarized right after
// the terminal stream event, so a summarized session parks a divider behind
// every turn including one paused on a HITL card. Walk back past both.
export function findActiveMessage(messages) {
	for (let i = messages.length - 1; i >= 0; i--) {
		const msg = messages[i];
		if (!msg?.queued && msg?.role !== "divider") return msg;
	}
	return undefined;
}
