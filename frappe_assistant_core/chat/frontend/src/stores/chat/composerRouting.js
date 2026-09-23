// Decides where a composer submit goes. Pending-card routing wins over
// streaming: a locally-pending card means the user's text is either the
// card's answer (question) or an abandon signal (approval).
export function resolveComposerRoute({ isStreaming, pendingInteraction }) {
	if (pendingInteraction) {
		return pendingInteraction.regime === "question" ? "answer" : "abort-then-send";
	}
	if (isStreaming) return "queue";
	return "send";
}
