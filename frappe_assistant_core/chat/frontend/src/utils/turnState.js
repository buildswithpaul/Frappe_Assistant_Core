/**
 * How an assistant turn that is no longer streaming should read. A turn paused
 * at an approval or question card is not streaming, but it has not ended
 * either: it is neither in flight nor stopped.
 */

import { isApprovalInteraction } from "@/stores/chat/interactionRegime";

// What a waiting turn says it waits on, for the card header and the widget strip.
export const WAITING_LABELS = {
	approval: "Waiting for your approval…",
	question: "Waiting for your answer…",
	resume: "Resuming…",
};

// A card the user has decided waits on the resume, not on the user.
function cardsAwaitingUser(blocks) {
	return Array.isArray(blocks)
		? blocks.filter((b) => b?.type === "interaction" && b.status === "pending" && !b.decision)
		: [];
}

export function isPausedTurn(blocks) {
	return cardsAwaitingUser(blocks).length > 0;
}

// "approval" or "question" while a card waits on the user (approval wins, as
// chatStore.pendingInteractionBlock decides), "resume" while an answered card's
// resume is in flight (chatStore.isSubmittingInterrupts), "" otherwise.
export function turnWaitingOn(blocks, resuming) {
	const cards = cardsAwaitingUser(blocks);
	if (cards.length) {
		return cards.some((b) => isApprovalInteraction(b.interactionType)) ? "approval" : "question";
	}
	return resuming ? "resume" : "";
}

// Stop sets `aborted` on the live message, and the row persists it (aborted=1).
// A card can still be pending on an aborted message when stream_aborted arrives
// without a blocks snapshot; that turn reads as paused, not stopped.
export function isStoppedTurn(message) {
	return Boolean(message?.aborted) && !isPausedTurn(message?.blocks);
}
