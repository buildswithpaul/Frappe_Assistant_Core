/**
 * Compose-while-streaming queue.
 *
 * Messages typed during a live turn are held here and dispatched one at a
 * time once the turn finalizes (complete, error, or user Stop) and no HITL
 * card is waiting. In-memory only — a reload drops the queue.
 */
import { ref, watch } from "vue";

export function createSendQueue({
	messages,
	currentSessionId,
	isStreaming,
	hasPendingInteraction,
	isSubmittingInterrupts,
	dispatch,
}) {
	const queuedMessages = ref([]);
	let queueSeq = 0;

	function queueMessage(message, files, context, modelId) {
		const item = {
			id: `q${++queueSeq}`,
			sessionId: currentSessionId.value,
			message,
			files,
			context,
			modelId,
		};
		queuedMessages.value.push(item);
		messages.value.push({
			role: "user",
			content: message,
			queued: true,
			_queueId: item.id,
			files: (files || []).map((f) => ({ name: f.file_name, url: f.file_url })),
			timestamp: new Date().toISOString(),
		});
	}

	function removeBubble(queueId) {
		messages.value = messages.value.filter((m) => m._queueId !== queueId);
	}

	function unqueueMessage(queueId) {
		queuedMessages.value = queuedMessages.value.filter((q) => q.id !== queueId);
		removeBubble(queueId);
	}

	async function dispatchQueued() {
		// isSubmittingInterrupts also gates a resume-in-flight window where
		// isStreaming/hasPendingInteraction have both already gone false but
		// the resumed turn hasn't produced its first event yet — see the
		// comment on isSubmittingInterrupts in chatStore's submitInterruptDecision.
		if (isStreaming.value || hasPendingInteraction.value || isSubmittingInterrupts.value) return;
		queuedMessages.value = queuedMessages.value.filter((q) => {
			if (q.sessionId === currentSessionId.value) return true;
			removeBubble(q.id);
			return false;
		});
		const next = queuedMessages.value.shift();
		if (!next) return;
		removeBubble(next.id);
		await dispatch(next);
	}

	watch(
		[isStreaming, hasPendingInteraction, isSubmittingInterrupts],
		([streaming, pending, submitting]) => {
			if (streaming || pending || submitting || !queuedMessages.value.length) return;
			// Defer so the finalization handlers that flipped these refs finish first.
			Promise.resolve().then(dispatchQueued);
		}
	);

	return { queuedMessages, queueMessage, unqueueMessage, dispatchQueued };
}
