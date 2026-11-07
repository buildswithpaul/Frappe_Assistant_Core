import { isApprovalInteraction } from "@/stores/chat/interactionRegime";
import { approvalLevel } from "@/utils/toolNames";

/**
 * A waiting approval that may be decided together with its siblings: an ordinary (R2) write.
 *
 * R3 always gets its own card. An approval with no level is not a leveled write (a BYO tool,
 * a customisation with its code preview, an email with its draft), so it keeps today's card:
 * approving those unseen is what the individual card exists to prevent.
 */
export function isBatchableApproval(block) {
	return (
		block.type === "interaction" &&
		block.status === "pending" &&
		isApprovalInteraction(block.interactionType) &&
		approvalLevel(block) === "R2"
	);
}

/** The approvals on one message that render as one card, or [] when fewer than two wait. */
export function findApprovalBatch(blocks) {
	const batch = (blocks || []).filter(isBatchableApproval);
	return batch.length >= 2 ? batch : [];
}
