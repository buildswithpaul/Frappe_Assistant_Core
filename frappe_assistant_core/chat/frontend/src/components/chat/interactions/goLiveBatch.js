import { isApprovalInteraction } from "@/stores/chat/interactionRegime";

/** A waiting approval that would put site-customisation code live (AR marks it risk "customisation"). */
export function isGoLiveApproval(block) {
	return (
		block.type === "interaction" &&
		block.status === "pending" &&
		isApprovalInteraction(block.interactionType) &&
		block.interrupts?.[0]?.reason?.risk === "customisation"
	);
}

/** The go-live approvals on one message that render as one card, or [] when fewer than two wait. */
export function findGoLiveBatch(blocks) {
	const batch = (blocks || []).filter(isGoLiveApproval);
	return batch.length >= 2 ? batch : [];
}
