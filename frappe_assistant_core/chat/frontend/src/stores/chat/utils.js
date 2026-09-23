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
