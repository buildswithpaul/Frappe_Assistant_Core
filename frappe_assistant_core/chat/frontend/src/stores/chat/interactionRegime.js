// Single source of truth for classifying a pending HITL interaction block.
// "approval" is the one special value (and the default when the field is
// absent) — every other value, including future ones like "text_input",
// "single_select", etc., is a question. Consumed by chatStore.js (composer
// routing regime) and InteractionCard.vue (which card component to render)
// so the two can't drift apart again.
export function isApprovalInteraction(interactionType) {
	return (interactionType || "approval") === "approval";
}
