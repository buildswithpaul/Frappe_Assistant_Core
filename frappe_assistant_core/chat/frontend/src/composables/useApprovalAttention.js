// A pending approval blocks the agent until the user answers it, but the card
// only exists inside the conversation view. Someone who switched tabs while
// the turn ran has no way to know they are the bottleneck — so flash the tab
// title while a decision is outstanding and the tab is hidden.
import { watch, onUnmounted } from "vue";

export const FLASH_INTERVAL_MS = 1200;

export function useApprovalAttention(chatStore) {
	let timer = null;
	let originalTitle = "";

	function stop() {
		if (!timer) return;
		clearInterval(timer);
		timer = null;
		if (originalTitle) document.title = originalTitle;
	}

	function start() {
		if (timer) return;
		originalTitle = document.title;
		let showing = false;
		timer = setInterval(() => {
			// Nothing to signal once the user is looking at the tab; the
			// approval card speaks for itself there.
			if (!document.hidden) {
				stop();
				return;
			}
			showing = !showing;
			document.title = showing ? "● Approval needed" : originalTitle;
		}, FLASH_INTERVAL_MS);
	}

	watch(
		() => chatStore.hasPendingInteraction,
		(pending) => (pending ? start() : stop()),
		{ immediate: true }
	);

	// Returning to the tab resolves the signal; leaving it re-arms one.
	function onVisibilityChange() {
		if (!document.hidden) stop();
		else if (chatStore.hasPendingInteraction) start();
	}
	document.addEventListener("visibilitychange", onVisibilityChange);

	onUnmounted(() => {
		document.removeEventListener("visibilitychange", onVisibilityChange);
		stop();
	});

	return { stop };
}
