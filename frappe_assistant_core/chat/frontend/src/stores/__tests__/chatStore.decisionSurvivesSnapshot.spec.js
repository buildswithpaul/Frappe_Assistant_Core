import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { mount } from "@vue/test-utils";
import { useChatStore } from "@/stores/chatStore";
import { call } from "frappe-ui";
import { api } from "@/api/client";
import InteractionCard from "@/components/chat/InteractionCard.vue";

vi.mock("@/api/client", () => ({
	api: { chat: { getMessages: vi.fn().mockResolvedValue({ messages: [] }), getLiveTurn: vi.fn() } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

/**
 * Live-bug repro (round 2, P1): a helper was still running when the approval
 * card arrived, so the original stream was still open when the user approved.
 * That stream then ended with stream_complete(interrupted), whose blocks
 * snapshot still holds the card `pending`. Adopting it wholesale brought the
 * Approve/Reject buttons back and the widget strip read "Waiting for your
 * approval…" until the resume arrived.
 */
describe("a decision made while the paused stream is still open", () => {
	let store;

	const snapshot = () => [
		{ type: "tool_call", id: "call_1", tool_name: "create_document", status: "running" },
		{ type: "interaction", id: "call_1", status: "pending", interactionType: "approval", interrupts: [{ id: "int1" }] },
	];

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
		store.currentSessionId = "s1";
		vi.clearAllMocks();
		// approval_required arrived on the still-streaming turn.
		store.isStreaming = true;
		store.messages = [{ role: "assistant", message_id: "m-1", isStreaming: true, blocks: snapshot() }];
		store.hasPendingInteraction = true;
	});

	const approve = () =>
		store.submitInterruptDecision({
			blockId: "call_1",
			resolution: "approved",
			userResponse: null,
			response: "approve",
		});
	const card = () => store.messages[0].blocks.find((b) => b.type === "interaction");
	const finishInterrupted = () =>
		store.completeStreaming("partial", { interrupted: true, blocks: snapshot() });

	it("keeps the approval when the interrupted stream ends after the resume was acknowledged", async () => {
		await approve();
		finishInterrupted();

		expect(card().status).toBe("approved");
		expect(card().decision?.resolution).toBe("approved");
		const rendered = mount(InteractionCard, { props: { block: card() } });
		expect(rendered.find(".ql-btn-approve").exists()).toBe(false);
	});

	it("keeps the approval when the interrupted stream ends before the resume is acknowledged", async () => {
		let acknowledge;
		call.mockImplementationOnce(() => new Promise((resolve) => (acknowledge = resolve)));
		const approving = approve();
		await vi.waitFor(() => expect(acknowledge).toBeTypeOf("function"));

		finishInterrupted();
		expect(card().decision?.resolution).toBe("approved");
		expect(mount(InteractionCard, { props: { block: card() } }).find(".ql-btn-approve").exists()).toBe(false);

		acknowledge({});
		await approving;
		// The status flip lands on the card on screen, not on the replaced one.
		expect(card().status).toBe("approved");
	});

	// A socket reconnect reconciles the session while the user works through a
	// batch of parallel cards: the first is decided locally, the batch has not
	// gone out, and the server row holds both cards pending.
	it("keeps a decision across a reconcile while the rest of the batch is undecided", async () => {
		const both = () => [
			...snapshot(),
			{ type: "interaction", id: "call_2", status: "pending", interactionType: "approval", interrupts: [{ id: "int2" }] },
		];
		store.isStreaming = false;
		store.messages = [{ role: "assistant", message_id: "m-1", content: "partial", blocks: both() }];
		await approve();
		expect(call).not.toHaveBeenCalled();
		api.chat.getMessages.mockResolvedValueOnce({
			messages: [{ role: "assistant", message_id: "m-1", content: "partial", blocks: both() }],
		});

		await store.reconcileFromServer("s1");

		expect(card().decision?.resolution).toBe("approved");
	});

	it("brings the buttons back when the resume is refused after the snapshot landed", async () => {
		let refuse;
		call.mockImplementationOnce(() => new Promise((_, reject) => (refuse = reject)));
		const approving = approve();
		await vi.waitFor(() => expect(refuse).toBeTypeOf("function"));
		finishInterrupted();

		refuse(new Error("resume_interrupt failed"));
		await approving;

		expect(card().decision).toBeFalsy();
		expect(card().status).toBe("pending");
		expect(mount(InteractionCard, { props: { block: card() } }).find(".ql-btn-approve").exists()).toBe(true);
	});
});
