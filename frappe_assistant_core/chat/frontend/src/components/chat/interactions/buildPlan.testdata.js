// Test data for build plan specs. Blocks are made by the real approval_required handler, so a
// spec sees the block shape the live stream produces, not one written by hand.
import { ref } from "vue";

import { createBlockHandlers } from "@/stores/chat/blockHandlers";

export const PLAN_ID = "0123456789abcdef0123456789abcdef";

// The reason AR raises from propose_build_plan (assistant_runtime/agent/build_plan.py).
export function planReason(overrides = {}) {
	return {
		type: "build_plan",
		plan_id: PLAN_ID,
		summary: "Track customer regions and show them on a Sales workspace.",
		changes: [
			{
				doctype: "Custom Field",
				action: "create",
				identity: { dt: "Customer", fieldname: "region" },
				description: "Adds a Region field to Customer, hidden until switched on.",
				goes_live: false,
			},
			{
				doctype: "Workspace",
				action: "create",
				name: "Sales Regions",
				description: "Adds a Sales Regions workspace to the sidebar.",
				goes_live: true,
			},
		],
		mockup_html: null,
		...overrides,
	};
}

// The approval_required event FAC's relay emits for that interrupt (chat/api/chat/relay.py).
export function planEvent(overrides = {}) {
	return {
		tool_id: "toolu_plan",
		tool_name: "propose_build_plan",
		input: {},
		interrupts: [{ id: "int-plan", name: "propose_build_plan", reason: planReason(overrides) }],
	};
}

export function planBlock(overrides = {}) {
	const messages = ref([{ role: "assistant", isStreaming: true, blocks: [], _requestId: "req-1" }]);
	const handlers = createBlockHandlers({
		messages,
		isStreaming: ref(true),
		hasPendingInteraction: ref(false),
		activeThinkingBlockId: ref(null),
		activeToolCallId: ref(null),
		streamRequestId: ref("req-1"),
	});
	handlers.handleApprovalRequired(planEvent(overrides));
	return messages.value[0].blocks.at(-1);
}
