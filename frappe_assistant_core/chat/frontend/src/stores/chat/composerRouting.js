// Decides where a composer submit goes. Pending-card routing wins over
// streaming: a locally-pending card means the user's text is either the
// card's answer (question) or an abandon signal (approval). Files can't ride
// along with an answer (the resume wire format has no attachment slot), so a
// submit with files leaves a question too and goes as a message of its own.
export function resolveComposerRoute({ isStreaming, pendingInteraction, hasFiles = false }) {
	if (pendingInteraction) {
		return pendingInteraction.regime === "question" && !hasFiles ? "answer" : "abort-then-send";
	}
	if (isStreaming) return "queue";
	return "send";
}
