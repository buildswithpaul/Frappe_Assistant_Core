import { computed } from "vue";
import { usePersonalLimitGate } from "@/composables/usePersonalLimitGate";

/**
 * FAC Chat's composer at the user's personal monthly limit, held as the Desk widget's is.
 *
 * AR admits every stream, a new message, a continue and a card answer alike, before it looks at the
 * team's credits, so each would come back as user_limit_reached. Holding them keeps the text in the
 * composer and lets the banner say what lifts the hold. Approval decisions are not wrapped here: one
 * AR refuses still shows the user_limit_reached notice.
 *
 * @param {{send: Function, continueTurn: Function}} handlers what to run when nothing holds them
 */
export function useComposerLimitHold({ send, continueTurn }) {
	const { block, recheck } = usePersonalLimitGate();
	const held = computed(() => Boolean(block.value));
	return {
		block,
		held,
		recheck,
		send: (payload) => (held.value ? false : send(payload)),
		continueTurn: (messageId) => (held.value ? false : continueTurn(messageId)),
	};
}
