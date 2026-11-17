import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { retryTarget } from "./chat/retryTurn";
import { isPausedTurn } from "@/utils/turnState";
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

	let thanksTimer = null;
	const marked = ref(false); // this card has started the fortnight clock
	let hosts = 0; // mounted ChatInterfaces that can render the card

	function latestAssistant() {
		const messages = useChatStore().messages;
		for (let i = messages.length - 1; i >= 0; i--) {
			if (messages[i]?.role === "assistant") return messages[i];
		}
		return null;
	}

	// Only a finished, quiet turn is a good moment: not streaming, not errored,
	// not stopped, not waiting on the user's approval or answer.
	function isBlocked() {
		const chat = useChatStore();
		const tour = useTourStore();
		if (chat.isStreaming || chat.errorCode || retryTarget(chat.messages)) return true;
		const last = latestAssistant();
		if (last?.aborted || isPausedTurn(last?.blocks)) return true;
		return tour.isOpen || tour.coachOpen || !!useSpotlightStore().current;
	}

	// A card not yet seen waits for a quiet turn, so a remount mid-stream never
	// shows it. Once it has rendered (marked) it stays, typed comment and all.
	const canRender = computed(() => visible.value && (marked.value || !isBlocked()));

	// A host that goes away before the card rendered takes the card with it:
	// nothing was shown, so nothing is marked, and the page session stays spent.
	function attach() {
		hosts += 1;
	}

	function detach() {
		hosts = Math.max(0, hosts - 1);
		if (hosts === 0 && visible.value && !marked.value) visible.value = false;
	}

	async function maybeShow() {
		if (consumed || visible.value) return;
		if (useUserStore().capabilities?.feedback_v2 !== true || isBlocked()) return;
		if (due === null) {
			try {
				due = (await api.feedback.pulseState())?.due === true;
			} catch (err) {
				logger.warn("Pulse state unavailable:", err);
				due = false;
			}
		}
		// The world can change during the await: re-check before showing.
		if (!due || consumed || isBlocked()) return;
		// With no host mounted nothing can show it: keep the page session (and the
		// cached answer) for a later turn on a mounted ChatInterface.
		if (hosts === 0) return;
		consumed = true;
		visible.value = true;
	}

	// Called by the card once it is on screen: only a rendered card starts the
	// fortnight clock.
	async function markShown() {
		if (marked.value) return;
		marked.value = true;
		try {
			await api.feedback.markPulseShown();
		} catch (err) {
			logger.warn("Failed to mark pulse shown:", err);
		}
	}

	function hide() {
		clearTimeout(thanksTimer);
		thanksTimer = null;
		visible.value = false;
		thanked.value = false;
		marked.value = false;
	}

	// An unanswered card belongs to the conversation it appeared in. It was
	// already marked shown and the page session stays consumed, so no re-ask.
	watch(
		() => useChatStore().currentSessionId,
		() => hide()
	);

	async function dismiss() {
		hide();
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
		clearTimeout(thanksTimer);
		thanksTimer = setTimeout(hide, THANKS_MS);
		return true;
	}

	return { visible, thanked, canRender, attach, detach, maybeShow, markShown, hide, dismiss, submit };
});
