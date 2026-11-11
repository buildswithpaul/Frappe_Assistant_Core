import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { call } from "frappe-ui";

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

// A worker that is restarting answers resume_interrupt with {status: "retry"} and queues
// nothing (#34895); the approval must be re-submitted, not left waiting on a stream.
const RETRY = { status: "retry", retry_after: 2, message: "Server restarting, retrying…" };
const PROCESSING = { status: "processing", session_id: "s1" };

describe("chatStore approval resume during a restart", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
		store.currentSessionId = "s1";
		vi.clearAllMocks();
		vi.useFakeTimers();
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
	const resumeCalls = () => call.mock.calls.filter(([m]) => m.endsWith("resume_interrupt"));
	const card = () => store.messages[0].blocks.find((b) => b.type === "interaction");

	it("re-submits once after retry_after, showing the restarting status", async () => {
		call.mockResolvedValueOnce(RETRY).mockResolvedValueOnce(PROCESSING);
		pauseOnAnApproval();

		const done = approve();
		await vi.advanceTimersByTimeAsync(0);
		expect(resumeCalls()).toHaveLength(1);
		expect(store.messages[0].statusNote).toBe("Server restarting, retrying…");

		await vi.advanceTimersByTimeAsync(2000);
		await done;

		expect(resumeCalls()).toHaveLength(2);
		expect(resumeCalls()[1][1]).toEqual(resumeCalls()[0][1]);
		expect(store.messages[0].statusNote).toBeFalsy();
		expect(card().status).toBe("approved");
		expect(store.isSubmittingInterrupts).toBe(true);
		expect(store.error).toBeFalsy();
	});

	it("a second retry shows the restart error and leaves the card to approve again", async () => {
		call.mockResolvedValueOnce(RETRY).mockResolvedValueOnce(RETRY);
		pauseOnAnApproval();

		const done = approve();
		await vi.advanceTimersByTimeAsync(2000);
		await done;

		expect(resumeCalls()).toHaveLength(2);
		expect(store.error).toBe("The server is restarting. Try again in a moment.");
		expect(store.errorCode).toBe("SERVER_RESTARTING");
		expect(store.messages[0].statusNote).toBeFalsy();
		expect(card().status).toBe("pending");
		expect(card().decision).toBeFalsy();
		expect(store.isSubmittingInterrupts).toBe(false);
	});
});
