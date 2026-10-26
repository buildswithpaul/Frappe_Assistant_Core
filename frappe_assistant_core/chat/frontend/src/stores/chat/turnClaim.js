// Open Full Assistant moves a conversation from the Desk widget to the chat app mid-turn. That turn
// keeps asking for the widget's browser tools, and the widget is gone. Claiming it tells the server
// to send this conversation's browser calls to the chat app until the next message (#34535).
import { ref, watch } from "vue";

import { logger } from "@/utils/logger";

/**
 * @param {{claim: (sessionId: string) => Promise<{claimed?: boolean}>, currentSessionId: import("vue").Ref<string|null>}} options
 */
export function createTurnClaim({ claim, currentSessionId }) {
	const claimedSession = ref(null);

	// The hand-over lands on a fresh page, so the claim may resolve before the conversation opens;
	// it ends only when this tab moves to another conversation.
	watch(currentSessionId, (id) => {
		if (claimedSession.value && id && id !== claimedSession.value) claimedSession.value = null;
	});

	async function claimLiveTurn(sessionId) {
		if (!sessionId) return false;
		try {
			const result = await claim(sessionId);
			if (result?.claimed) claimedSession.value = sessionId;
			return Boolean(result?.claimed);
		} catch (e) {
			// Not critical: the widget's call times out as it did before the claim existed.
			logger.warn("Claiming the live turn failed:", e);
			return false;
		}
	}

	/** Whether this tab took over `sessionId`'s running turn from the widget and still holds it. */
	function isClaimedLiveTurn(sessionId) {
		return Boolean(sessionId) && claimedSession.value === sessionId && currentSessionId.value === sessionId;
	}

	/** A turn this tab sends names its own client; the server drops the claim with it. */
	function releaseClaim() {
		claimedSession.value = null;
	}

	return { claimedSession, claimLiveTurn, isClaimedLiveTurn, releaseClaim };
}
