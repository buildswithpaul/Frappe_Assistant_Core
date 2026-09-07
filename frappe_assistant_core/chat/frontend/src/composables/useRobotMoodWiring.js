/**
 * Wires chat-app signals into the robot mood store.
 *
 * Install once at the chat root (ChatView). It sets up watchers that:
 *  - mirror chatStore.isStreaming → mood "thinking"
 *  - mirror chatStore.error      → mood "concerned"
 *  - detect unresolved interaction blocks (HITL approval) → "concerned"
 *  - pulse "delighted" when streaming completes successfully or the user
 *    sends a thanks-flavored message
 *  - pulse "excited" on the first user message of a session
 *
 * Cleans up its own watchers via `onScopeDispose` — safe to mount/unmount
 * with the chat view.
 */

import { onScopeDispose, watch } from "vue";
import { storeToRefs } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { useRobotMoodStore } from "@/stores/robotMoodStore";

const THANKS_RE = /\b(thanks?|thank you|thx|ty|appreciate|awesome|nice work|good job|love it)\b/i;

function _hasUnresolvedInteraction(messages) {
	if (!Array.isArray(messages) || messages.length === 0) return false;
	// Walk backwards — the freshest unresolved interaction is what matters.
	// An interaction block is unresolved when it has interrupts and no
	// `responded` flag set on the block.
	for (let i = messages.length - 1; i >= 0; i--) {
		const blocks = messages[i]?.blocks;
		if (!Array.isArray(blocks)) continue;
		for (const b of blocks) {
			if (b?.type === "interaction" && !b.responded) return true;
		}
	}
	return false;
}

export function useRobotMoodWiring() {
	const chat = useChatStore();
	const mood = useRobotMoodStore();
	const { isStreaming, error, messages } = storeToRefs(chat);

	let prevStreaming = isStreaming.value;
	let prevUserMsgCount = (messages.value || []).filter((m) => m.role === "user").length;

	const stopStreaming = watch(isStreaming, (val) => {
		mood.setStreaming(!!val);
		// streaming false after being true → response landed.
		// Only pulse delighted if we didn't error out.
		if (prevStreaming && !val && !error.value) {
			mood.pulseDelighted();
		}
		prevStreaming = !!val;
	});

	const stopError = watch(error, (val) => {
		mood.setHasError(!!val);
	});

	const stopMessages = watch(
		messages,
		(arr) => {
			const list = arr || [];
			mood.setAwaitingApproval(_hasUnresolvedInteraction(list));

			const userMsgs = list.filter((m) => m.role === "user");
			const newCount = userMsgs.length;

			if (newCount > prevUserMsgCount) {
				const newest = userMsgs[userMsgs.length - 1];
				const text = (newest?.content || "").toString();

				// First user message of a session → small celebration
				if (newCount === 1) {
					mood.pulseExcited();
				}

				// "thanks" → next-message-cycle delighted glow
				if (THANKS_RE.test(text)) {
					mood.pulseDelighted();
				}
			}

			prevUserMsgCount = newCount;
		},
		{ deep: true }
	);

	onScopeDispose(() => {
		stopStreaming();
		stopError();
		stopMessages();
		// Reset transient state so the next mount starts clean.
		mood.setStreaming(false);
		mood.setAwaitingApproval(false);
		mood.setHasError(false);
	});
}
