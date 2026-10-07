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

async function toolRow(blocks, { isResuming = false } = {}) {
	const wrapper = mount(MessageBlockRenderer, {
		props: { blocks, messageIndex: 0, isStreaming: false, isResuming },
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

// After the user approves, applyInteractionDecisions flips the card to
// `approved` at once, but the message stays non-streaming until the resume
// stream's first event (handleStreamResumed). isSubmittingInterrupts spans
// exactly that round trip.
describe("MessageBlockRenderer tool rows while a resume is in flight", () => {
	const APPROVED_CARD = { ...PENDING_CARD, status: "approved" };

	beforeEach(() => setActivePinia(createPinia()));

	it("keeps the just-approved tool from reading as stopped", async () => {
		const row = await toolRow([GATED_TOOL, APPROVED_CARD], { isResuming: true });

		expect(row.classes()).toContain("timeline-running");
		expect(row.find(".chip-stopped").exists()).toBe(false);
	});

	it("reads as stopped once the resume is no longer in flight", async () => {
		const row = await toolRow([GATED_TOOL, APPROVED_CARD, ABORT_MARKER]);

		expect(row.classes()).toContain("timeline-stopped");
	});
});
