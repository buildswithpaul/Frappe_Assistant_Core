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
