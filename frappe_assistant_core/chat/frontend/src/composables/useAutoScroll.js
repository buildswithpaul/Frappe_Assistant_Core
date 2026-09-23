import { ref, watch, nextTick, onMounted, onBeforeUnmount } from "vue";
import { findActiveMessage } from "@/stores/chat/utils";

// How far from the bottom (in px) still counts as "the user is following along".
// Tuned so a couple of lines of slack don't disengage follow-mode, but a
// deliberate scroll up (more than ~half a screen) does.
const FOLLOW_THRESHOLD_PX = 120;

/**
 * Auto-scroll a container to the bottom when messages change or new chunks
 * stream in — but only while the user is "following" (i.e. is already at or
 * very near the bottom). The moment the user scrolls up to read history,
 * we disengage follow-mode and stop yanking them back down; re-engage
 * automatically the next time they scroll to the bottom.
 *
 * Without this guard, every stream chunk fires ``scrollTop = scrollHeight``
 * which makes scrolling up during a stream functionally impossible.
 *
 * @param {import('vue').Ref<HTMLElement|null>} containerRef - ref to the scrollable element
 * @param {import('vue').Ref<Array>} messages - ref to the messages array (reactive source)
 * @param {import('vue').Ref<boolean>} isStreaming - ref indicating whether a stream is active
 */
export function useAutoScroll(containerRef, messages, isStreaming) {
	// We treat the user as "following" by default, and disengage when they
	// scroll up. A user-initiated scroll back to the bottom re-engages.
	const isFollowing = ref(true);

	function isAtBottom(el) {
		// Allow a small slack — sub-pixel layout, padding, and the typical
		// "I just sent a message and it scrolled itself" all land within a
		// few px of true bottom.
		return el.scrollHeight - el.scrollTop - el.clientHeight <= FOLLOW_THRESHOLD_PX;
	}

	function scrollToBottom() {
		const el = containerRef.value;
		if (!el) return;
		el.scrollTop = el.scrollHeight;
	}

	function onScroll() {
		const el = containerRef.value;
		if (!el) return;
		// Track user intent: if they scroll to the bottom, re-engage follow.
		// If they scroll away from the bottom, disengage. Programmatic scrolls
		// from this composable also fire 'scroll', but they always land at the
		// bottom — so they keep isFollowing=true, which is what we want.
		isFollowing.value = isAtBottom(el);
	}

	onMounted(() => {
		const el = containerRef.value;
		if (el) {
			el.addEventListener("scroll", onScroll, { passive: true });
		}
	});

	onBeforeUnmount(() => {
		const el = containerRef.value;
		if (el) {
			el.removeEventListener("scroll", onScroll);
		}
	});

	// New message added — always scroll. Sending a message is an explicit
	// user action that resets intent (you want to see your own message land).
	watch(
		() => messages.value.length,
		() => {
			isFollowing.value = true;
			nextTick(scrollToBottom);
		}
	);

	// Streaming chunks — only scroll if the user hasn't scrolled away.
	// Trigger on the last message's content length so block-expand toggles
	// don't re-fire this.
	watch(
		() =>
			isStreaming.value && (findActiveMessage(messages.value)?.content?.length ?? 0),
		() => {
			if (!isStreaming.value || !isFollowing.value) return;
			nextTick(scrollToBottom);
		}
	);

	return { isFollowing, scrollToBottom };
}
