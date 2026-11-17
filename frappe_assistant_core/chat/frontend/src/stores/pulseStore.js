import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { retryTarget } from "./chat/retryTurn";
import { useChatStore } from "./chatStore";
import { useSpotlightStore } from "./spotlightStore";
import { useTourStore } from "./tourStore";
import { useUserStore } from "./userStore";

const THANKS_MS = 3000;

/**
 * The periodic "How is FACO doing?" card.
 *
 * Errors from these endpoints never reach the user: an unreadable pulse_state
 * means "not due", a failed mark/dismiss is logged, only a failed submit is
 * reported (the card stays so the user can retry). pulse_state is asked at
 * most once per page session; the answer is cached either way.
 */
export const usePulseStore = defineStore("pulse", () => {
	const visible = ref(false);
	const thanked = ref(false);
	let due = null; // null = not asked yet this page session
	let consumed = false; // the card has been shown this page session

	function blocked() {
		const chat = useChatStore();
		const tour = useTourStore();
		if (chat.errorCode || retryTarget(chat.messages)) return true;
		return tour.isOpen || tour.coachOpen || !!useSpotlightStore().current;
	}

	async function maybeShow() {
		if (consumed || visible.value) return;
		if (useUserStore().capabilities?.feedback_v2 !== true || blocked()) return;
		if (due === null) {
			try {
				due = (await api.feedback.pulseState())?.due === true;
			} catch (err) {
				logger.warn("Pulse state unavailable:", err);
				due = false;
			}
		}
		// The world can change during the await: re-check before showing.
		if (!due || consumed || blocked()) return;
		consumed = true;
		visible.value = true;
		try {
			await api.feedback.markPulseShown();
		} catch (err) {
			logger.warn("Failed to mark pulse shown:", err);
		}
	}

	async function dismiss() {
		visible.value = false;
		try {
			await api.feedback.dismissPulse();
		} catch (err) {
			logger.warn("Failed to dismiss pulse:", err);
		}
	}

	// Resolves to whether the rating was stored.
	async function submit({ rating, comment = null, contactOk = false }) {
		try {
			await api.feedback.submitPulse({ rating, comment, contactOk });
		} catch (err) {
			logger.warn("Failed to submit pulse:", err);
			return false;
		}
		thanked.value = true;
		setTimeout(() => {
			visible.value = false;
			thanked.value = false;
		}, THANKS_MS);
		return true;
	}

	return { visible, thanked, maybeShow, dismiss, submit };
});
