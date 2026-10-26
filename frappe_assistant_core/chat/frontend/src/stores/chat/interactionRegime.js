// Single source of truth for classifying a pending HITL interaction block.
// "approval" is the one special value (and the default when the field is
// absent) — every other value, including future ones like "text_input",
// "single_select", etc., is a question. Consumed by chatStore.js (composer
// routing regime) and InteractionCard.vue (which card component to render)
// so the two can't drift apart again.
export function isApprovalInteraction(interactionType) {
	return (interactionType || "approval") === "approval";
}

// A build plan card answers like a question: typed feedback resolves it as not approved.
export function isBuildPlanInteraction(interactionType) {
	return interactionType === "build_plan";
}

// The one response that approves a build plan; AR treats anything else as not approved.
export function isPlanApproval(response) {
	return response?.decision === "approve";
}

// A card's response as the resolution its block takes once the resume is sent.
export function resolutionFor(response) {
	if (response === "trust") return "trusted";
	if (response === "rejected") return "rejected";
	if (response === "approve" || isPlanApproval(response)) return "approved";
	return "answered";
}
