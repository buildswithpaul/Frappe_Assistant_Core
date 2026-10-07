import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import MessageBlockRenderer from "@/components/chat/MessageBlockRenderer.vue";

// AR emits tool_call_start for the model's tool use before the approval hook
// interrupts it, so a turn paused at a card holds the gated tool as `running`.
const GATED_TOOL = {
	type: "tool_call",
	id: "tu-1",
	tool_name: "create_document",
	input: { doctype: "Quotation" },
	status: "running",
	startTime: "2026-07-20T09:00:00.000Z",
	endTime: null,
};
const PENDING_CARD = {
	type: "interaction",
	id: "tu-1",
	interactionType: "approval",
	tool_name: "create_document",
	input: { doctype: "Quotation" },
	interrupts: [],
	status: "pending",
};
const ABORT_MARKER = { type: "text", id: "m1", content: "\n\n_(Stopped by user)_", _abortMarker: true };

async function toolRow(blocks) {
	const wrapper = mount(MessageBlockRenderer, {
		props: { blocks, messageIndex: 0, isStreaming: false },
	});
	await wrapper.find(".processing-card-header").trigger("click");
	return wrapper.find(".timeline-row");
}

describe("MessageBlockRenderer tool rows once the message stops streaming", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("keeps a turn paused at a card from reading as stopped", async () => {
		const row = await toolRow([GATED_TOOL, PENDING_CARD]);

		expect(row.classes()).toContain("timeline-running");
		expect(row.classes()).not.toContain("timeline-stopped");
	});

	it("presents a stopped turn's tool left running as stopped", async () => {
		const row = await toolRow([GATED_TOOL, ABORT_MARKER]);

		expect(row.classes()).toContain("timeline-stopped");
	});

	it("presents a finished turn's tool left running as stopped", async () => {
		const row = await toolRow([GATED_TOOL]);

		expect(row.classes()).toContain("timeline-stopped");
	});
});
