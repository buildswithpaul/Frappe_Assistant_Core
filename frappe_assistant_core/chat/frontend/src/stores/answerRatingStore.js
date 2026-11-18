import { defineStore } from "pinia";
import { ref, watch } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { useUserStore } from "./userStore";

/**
 * The caller's 👍/👎 on assistant answers, keyed by message_id.
 *
 * Optimistic: state changes on click. Calls for one message are serialised so
 * AR receives them in click order; only the latest call's outcome drives a
 * revert, and it reverts to the last state AR confirmed. A locked rating
 * (support already triaged it) is re-read from the server so the UI never
 * shows a state AR didn't store.
 */
export const useAnswerRatingStore = defineStore("answerRating", () => {
	const userStore = useUserStore();
	const ratings = ref({});
	let loadedSessionId = null;
	// What AR last confirmed per message; revert target for a failed call.
	let confirmed = {};
	const chains = {};
	const latestCall = {};
	const pendingCalls = {};

	const feedbackEnabled = () => userStore.capabilities?.feedback_v2 === true;

	async function load(sessionId) {
		loadedSessionId = sessionId;
		if (!feedbackEnabled()) {
			ratings.value = {};
			confirmed = {};
			return;
		}
		try {
			const result = (await api.feedback.answerRatings(sessionId)) || {};
			if (loadedSessionId !== sessionId) return;
			// A message with a call in flight keeps its optimistic state.
			const next = { ...result };
			const nextConfirmed = { ...result };
			for (const id of Object.keys(pendingCalls)) {
				if (!pendingCalls[id]) continue;
				if (ratings.value[id]) next[id] = ratings.value[id];
				else delete next[id];
				if (confirmed[id]) nextConfirmed[id] = confirmed[id];
				else delete nextConfirmed[id];
			}
			ratings.value = next;
			confirmed = nextConfirmed;
		} catch (err) {
			logger.warn("Failed to load answer ratings:", err);
			if (loadedSessionId !== sessionId) return;
			ratings.value = {};
			confirmed = {};
		}
	}

	// A rating that arrives after the capabilities do (boot order is not fixed).
	watch(
		() => userStore.capabilities?.feedback_v2 === true,
		(enabled) => {
			if (enabled && loadedSessionId) load(loadedSessionId);
		}
	);

	function setRating(messageId, rating) {
		const next = { ...ratings.value };
		if (rating) next[messageId] = rating;
		else delete next[messageId];
		ratings.value = next;
	}

	function setConfirmed(messageId, rating) {
		if (rating) confirmed[messageId] = rating;
		else delete confirmed[messageId];
	}

	// Queue one call behind the message's earlier calls; resolves to true when
	// it was the latest click and so owns the final state.
	function enqueue(messageId, optimistic, call) {
		const wasIdle = !pendingCalls[messageId];
		if (wasIdle) setConfirmed(messageId, ratings.value[messageId]);
		const callId = (latestCall[messageId] || 0) + 1;
		latestCall[messageId] = callId;
		pendingCalls[messageId] = (pendingCalls[messageId] || 0) + 1;
		setRating(messageId, optimistic);

		const run = async () => {
			let outcome = { ok: false };
			try {
				outcome = { ok: true, result: await call() };
			} catch (err) {
				logger.warn("Answer rating call failed:", err);
			}
			pendingCalls[messageId] -= 1;
			if (outcome.ok && !outcome.result?.locked) setConfirmed(messageId, optimistic);
			if (latestCall[messageId] !== callId) return;
			if (!outcome.ok) {
				setRating(messageId, confirmed[messageId]);
			} else if (outcome.result?.locked) {
				setRating(messageId, confirmed[messageId]);
				if (loadedSessionId) await load(loadedSessionId);
			}
		};
		chains[messageId] = (chains[messageId] || Promise.resolve()).then(run);
		return chains[messageId];
	}

	function rate(messageId, reaction, reasons = [], comment = null) {
		return enqueue(messageId, { reaction, reasons }, () =>
			api.feedback.rateAnswer({ messageId, reaction, reasons, comment })
		);
	}

	function withdraw(messageId) {
		// withdrawn: false means AR kept it; the user's view stays cleared.
		return enqueue(messageId, null, () => api.feedback.withdrawAnswerRating(messageId));
	}

	return { ratings, load, rate, withdraw };
});
