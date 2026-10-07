/**
 * How an assistant turn that is no longer streaming should read. A turn paused
 * at an approval or question card is not streaming, but it has not ended
 * either: it is neither in flight nor stopped.
 */

// A card the user has decided waits on the resume, not on the user.
export function isPausedTurn(blocks) {
	return (
		Array.isArray(blocks) &&
		blocks.some((b) => b?.type === "interaction" && b.status === "pending" && !b.decision)
	);
}

// Stop sets `aborted` on the live message, and the row persists it (aborted=1).
// A card can still be pending on an aborted message when stream_aborted arrives
// without a blocks snapshot; that turn reads as paused, not stopped.
export function isStoppedTurn(message) {
	return Boolean(message?.aborted) && !isPausedTurn(message?.blocks);
}
