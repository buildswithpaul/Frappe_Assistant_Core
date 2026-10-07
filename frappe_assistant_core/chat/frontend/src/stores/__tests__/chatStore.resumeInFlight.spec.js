import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: {
		chat: {
			send: vi.fn().mockResolvedValue({}),
			getMessages: vi.fn().mockResolvedValue({ messages: [] }),
			getLiveTurn: vi.fn().mockResolvedValue(null),
		},
	},
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

/**
 * isSubmittingInterrupts spans an approved card's resume round trip: the
 * resume POST only queues the resume, and the flag clears on the resume
 * stream's first event (or its error/abort). While it is set the latest
 * turn's tools spin and the widget reads "Resuming…", so it must not outlive
 * a session switch or a resume that never produces an event.
 */
describe("chatStore resume in flight", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
		store.currentSessionId = "s1";
		vi.clearAllMocks();
	});

	afterEach(() => vi.useRealTimers());

	// The shape a paused turn has: AR announced the gated tool, then the
	// approval hook interrupted it and the stream completed as interrupted.
	function pauseOnAnApproval() {
		const blocks = [
			{ type: "tool_call", id: "call_1", tool_name: "create_document", status: "running" },
			{
				type: "interaction",
				id: "call_1",
				status: "pending",
				interactionType: "approval",
				interrupts: [{ id: "int1" }],
			},
		];
		store.messages = [{ role: "assistant", message_id: "m-1", blocks }];
		store.hasPendingInteraction = true;
		store.completeStreaming("partial", { interrupted: true, blocks });
	}

	const approve = () =>
		store.submitInterruptDecision({
			blockId: "call_1",
			resolution: "approved",
			userResponse: null,
			response: "approve",
		});

	it("clears when the user switches to another session", async () => {
		pauseOnAnApproval();
		await approve();
		expect(store.isSubmittingInterrupts).toBe(true);

		await store.loadMessages("s2");

		expect(store.isSubmittingInterrupts).toBe(false);
	});

	it("times out a resume that never produces an event", async () => {
		vi.useFakeTimers();
		pauseOnAnApproval();
		await approve();
		expect(store.isSubmittingInterrupts).toBe(true);
		// The pre-timeout reconcile finds nothing newer on the server.
		api.chat.getMessages.mockRejectedValueOnce(new Error("offline"));

		await vi.advanceTimersByTimeAsync(180000);

		expect(store.isSubmittingInterrupts).toBe(false);
		expect(store.error).toMatch(/No response received/);
		const tool = store.messages[0].blocks.find((b) => b.type === "tool_call");
		expect(tool.status).toBe("error");
	});
});
