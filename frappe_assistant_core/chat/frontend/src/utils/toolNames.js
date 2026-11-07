/**
 * Tool-name and interrupt helpers shared by the stores, composables and approval cards.
 */

// A second connection's tools arrive prefixed ("prod_create_document"); the base name decides.
const WRITE_TOOL_NAMES = ["create_document", "update_document", "delete_document", "document_action"];

export function baseToolName(toolName) {
	if (typeof toolName !== "string") return "";
	return WRITE_TOOL_NAMES.find((name) => toolName === name || toolName.endsWith(`_${name}`)) || toolName;
}

// AR flags writes to customisation doctypes on the interrupt reason.
export function isCustomisationRisk(block) {
	return block?.interrupts?.[0]?.reason?.risk === "customisation";
}

// AR's approval level for a leveled write ("R2" or "R3"); absent for every other approval.
export function approvalLevel(block) {
	return block?.interrupts?.[0]?.reason?.level ?? null;
}

// "Don't ask again" is never offered where AR would still ask: customisations and R3 writes.
export function canTrust(block) {
	return !isCustomisationRisk(block) && approvalLevel(block) !== "R3";
}
