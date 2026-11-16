// The latest turn can be retried when it ended in an error, an interruption included
// (mark_turn_interrupted persists it errored). Returns where its answer sits and the user
// message it answers (persisted, so it has a name), or null. A turn that completed or was stopped is never offered.
export function retryTarget(messages) {
	for (let i = messages.length - 1; i >= 0; i--) {
		const msg = messages[i];
		if (msg?.role === "user") return null;
		if (msg?.role !== "assistant") continue;
		if (!msg.errored || msg.aborted || msg.isStreaming) return null;
		for (let j = i - 1; j >= 0; j--) {
			// A message this surface pushed has no row name until the history is re-read.
			if (messages[j]?.role === "user") return messages[j].name ? { index: i, userMessage: messages[j].name } : null;
		}
		return null;
	}
	return null;
}
