import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { call } from "frappe-ui";

vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));
vi.mock("@/api/client", () => ({
	api: {
		chat: { getMessages: vi.fn(), getLiveTurn: vi.fn() },
		tools: {
			messagePreview: vi.fn(),
			currentCode: vi.fn().mockRejectedValue(new Error("not fetched")),
			fieldPlacement: vi.fn().mockRejectedValue(new Error("not fetched")),
			codeGoingLive: vi.fn().mockResolvedValue([]),
		},
	},
}));

import BatchedApprovalCard from "./BatchedApprovalCard.vue";
import { useChatStore } from "@/stores/chatStore";
import { resolutionFor } from "@/stores/chat/interactionRegime";

// Two parallel create_document calls AR gated at R2, as the stream delivers them: one card each.
const r2Card = (id, title) => ({
	type: "interaction",
	id,
	interactionType: "approval",
	tool_name: "create_document",
	input: { doctype: "Note", data: { title } },
	status: "pending",
	interrupts: [{ id: `i-${id}`, reason: { type: "approval", level: "R2" } }],
});

let store;

beforeEach(() => {
	setActivePinia(createPinia());
	localStorage.clear();
	store = useChatStore();
	store.currentSessionId = "s1";
	vi.mocked(call).mockClear();
});

// Wired as ChatView wires the card's events: each decision goes to submitInterruptDecision.
function mountBatch() {
	store.messages = [
		{ role: "assistant", message_id: "m1", isStreaming: true, blocks: [r2Card("a", "First"), r2Card("b", "Second")] },
	];
	const decide = (blockId, responses) =>
		store.submitInterruptDecision({
			blockId,
			resolution: resolutionFor(responses[0].response),
			userResponse: responses[0].response,
			response: responses[0].response,
		});
	return mount(BatchedApprovalCard, {
		props: { blocks: store.messages[0].blocks, submitting: false },
		attrs: { onApprove: decide, onReject: decide },
		global: { stubs: { InteractionCard: { props: ["block"], template: `<div class="single-card" />` } } },
	});
}

const button = (wrapper, label) => wrapper.findAll("button").find((b) => b.text() === label);
const resumeCalls = () => vi.mocked(call).mock.calls.filter(([method]) => method.endsWith("resume_interrupt"));

describe("BatchedApprovalCard", () => {
	it("shows one line per write", () => {
		const wrapper = mountBatch();
		const lines = wrapper.findAll(".bac-item");
		expect(lines).toHaveLength(2);
		expect(lines[0].text()).toContain("First");
		expect(lines[1].text()).toContain("Second");
		expect(wrapper.find(".trust-choice").exists()).toBe(false);
	});

	it("approve all decides every block once", async () => {
		const wrapper = mountBatch();
		await button(wrapper, "Approve all").trigger("click");
		await flushPromises();

		expect(wrapper.emitted("approve")).toEqual([
			["a", [{ interruptId: "i-a", response: "approve" }]],
			["b", [{ interruptId: "i-b", response: "approve" }]],
		]);
		expect(resumeCalls()).toHaveLength(1);
		expect(JSON.parse(resumeCalls()[0][1].interrupt_response)).toEqual([
			{ interruptId: "i-a", response: "approve" },
			{ interruptId: "i-b", response: "approve" },
		]);
	});

	it("reject all decides every block reject", async () => {
		const wrapper = mountBatch();
		await button(wrapper, "Reject all").trigger("click");
		await flushPromises();

		expect(wrapper.emitted("reject").map(([id, r]) => [id, r[0].response])).toEqual([
			["a", "rejected"],
			["b", "rejected"],
		]);
		expect(resumeCalls()).toHaveLength(1);
	});

	it("review each expands the individual cards", async () => {
		const wrapper = mountBatch();
		await button(wrapper, "Review each").trigger("click");
		expect(wrapper.findAll(".single-card")).toHaveLength(2);
		expect(button(wrapper, "Approve all")).toBeUndefined();
	});

	it("approve all skips a block already decided", async () => {
		const wrapper = mountBatch();
		store.messages[0].blocks[0].decision = { resolution: "rejected", responses: [{ interruptId: "i-a", response: "rejected" }] };
		await button(wrapper, "Approve all").trigger("click");
		expect(wrapper.emitted("approve")).toEqual([["b", [{ interruptId: "i-b", response: "approve" }]]]);
	});
});
