import { __ } from "@/utils/i18n";

/**
 * The plan a build_plan card shows: AR's interrupt reason, which the block keeps in its
 * interrupts both live and when the turn is reloaded from the saved message.
 */
export function planOf(block) {
	const reason = block?.interrupts?.[0]?.reason || {};
	return {
		planId: reason.plan_id || "",
		summary: reason.summary || "",
		changes: Array.isArray(reason.changes) ? reason.changes : [],
		mockupHtml: reason.mockup_html || "",
	};
}

/** Changes that go live first, so they are read before the dormant ones. */
export function groupChanges(changes) {
	const live = changes.filter((c) => c.goes_live);
	const dormant = changes.filter((c) => !c.goes_live);
	return [
		{ live: true, changes: live },
		{ live: false, changes: dormant },
	].filter((g) => g.changes.length);
}

/** The record a change touches: its name, or its identity read out (e.g. "Customer · region"). */
export function changeRecord(change) {
	if (change.name) return String(change.name);
	const identity = change.identity && typeof change.identity === "object" ? change.identity : {};
	return Object.values(identity)
		.filter((v) => v !== null && v !== undefined && v !== "")
		.join(" · ");
}

export function actionLabel(action) {
	if (action === "create") return __("Create");
	if (action === "update") return __("Update");
	if (action === "delete") return __("Delete");
	return String(action || "");
}

/** The responses that approve this plan, one per interrupt the card owns. */
export function approvalResponses(block) {
	const { planId } = planOf(block);
	return (block.interrupts || []).map((i) => ({
		interruptId: i.id,
		response: { decision: "approve", plan_id: planId },
	}));
}
