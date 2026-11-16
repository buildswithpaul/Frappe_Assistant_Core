import { isApprovalInteraction, isBuildPlanInteraction } from "@/stores/chat/interactionRegime";

/**
 * What the user answered a question FACO asked with, as text, or "" when the block is no
 * answered question: an approval, a build plan, one still waiting or skipped (#34546).
 */
export function userAnswer(block) {
	if (block?.type !== "interaction" || block.status === "pending") return "";
	if (isApprovalInteraction(block.interactionType) || isBuildPlanInteraction(block.interactionType)) return "";
	const answer = block.userResponse;
	if (Array.isArray(answer)) return answer.join(", ");
	return answer == null ? "" : String(answer).trim();
}
