import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { useUserStore } from "./userStore";

/**
 * The caller's 👍/👎 on assistant answers, keyed by message_id.
 *
 * Optimistic: state changes on click and reverts when the call fails. When AR
 * reports the stored rating is locked (support already triaged it), the state
 * is re-read from the server so the UI never shows a rating AR didn't store.
 */
export const useAnswerRatingStore = defineStore("answerRating", () => {
	const ratings = ref({});
	let loadedSessionId = null;

	async function load(sessionId) {
		loadedSessionId = sessionId;
		if (useUserStore().capabilities?.feedback_v2 !== true) {
			ratings.value = {};
			return;
		}
		try {
			const result = await api.feedback.answerRatings(sessionId);
			if (loadedSessionId === sessionId) ratings.value = result || {};
		} catch (err) {
			logger.warn("Failed to load answer ratings:", err);
			ratings.value = {};
		}
	}

	function restore(messageId, previous) {
		const next = { ...ratings.value };
		if (previous) next[messageId] = previous;
		else delete next[messageId];
		ratings.value = next;
	}

	async function rate(messageId, reaction, reasons = [], comment = null) {
		const previous = ratings.value[messageId];
		ratings.value = { ...ratings.value, [messageId]: { reaction, reasons } };
		try {
			const result = await api.feedback.rateAnswer({ messageId, reaction, reasons, comment });
			if (result?.locked) {
				restore(messageId, previous);
				if (loadedSessionId) await load(loadedSessionId);
			}
		} catch (err) {
			logger.warn("Failed to save answer rating:", err);
			restore(messageId, previous);
		}
	}

	async function withdraw(messageId) {
		const previous = ratings.value[messageId];
		restore(messageId, null);
		try {
			// withdrawn: false means AR kept it; the user's view stays cleared.
			await api.feedback.withdrawAnswerRating(messageId);
		} catch (err) {
			logger.warn("Failed to withdraw answer rating:", err);
			restore(messageId, previous);
		}
	}

	return { ratings, load, rate, withdraw };
});
