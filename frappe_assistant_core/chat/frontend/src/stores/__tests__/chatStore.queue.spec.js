import { describe, it, expect, vi, beforeEach } from "vitest";
import { nextTick } from "vue";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: {
		chat: {
			getMessages: vi.fn(),
			cancelStream: vi.fn().mockResolvedValue({}),
			send: vi.fn().mockResolvedValue({}),
		},
	},
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

// Lets the queue watcher's deferred (Promise.resolve().then) dispatch chain settle.
const flush = () => new Promise((r) => setTimeout(r, 0));

describe("chatStore send queueing", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
		store.currentSessionId = "s1";
		vi.clearAllMocks();
	});

	it("sendMessage queues instead of sending while streaming", async () => {
		store.isStreaming = true;
		await store.sendMessage("later please", [], null, "m1");
		expect(store.queuedMessages).toHaveLength(1);
		expect(store.messages.find((m) => m._queueId)?.content).toBe("later please");
	});

	it("does not queue a send that follows abortPendingInteraction, even though isStreaming is still true", async () => {
		// Task 7 discovery: isStreaming stays true for the whole HITL pause, and
		// abortPendingInteraction() never flips it back either — only the
		// eventual stream_aborted/stream_error socket event does. The composer's
		// abort-then-send route can't tell sendMessage apart from a plain queue
		// candidate by reading ambient refs; it must say so explicitly.
		store.messages = [
			{
				role: "assistant",
				message_id: "m1",
				blocks: [
					{
						type: "interaction",
						id: "blk1",
						status: "pending",
						interactionType: "approval",
						interrupts: [{ id: "int1" }],
					},
				],
			},
		];
		store.isStreaming = true;
		expect(store.pendingInteractionBlock.regime).toBe("approval");

		await store.abortPendingInteraction();
		// The hazard, made concrete: isStreaming was never flipped by the abort.
		expect(store.isStreaming).toBe(true);

		await store.sendMessage("new message now", [], null, "m1", null, { skipQueue: true });

		expect(api.chat.send).toHaveBeenCalled();
		expect(store.queuedMessages).toHaveLength(0);
		expect(
			store.messages.find((m) => m.role === "user" && m.content === "new message now")
		).toBeTruthy();
	});

	it("does not dispatch a queued message into the gap between an approval's resume_interrupt ack and the resume stream's first event", async () => {
		// Live-bug repro (e2e-3): essay streams -> user queues a message ->
		// agent hits a gated tool -> approval card pauses the turn -> user
		// clicks Approve -> resume_interrupt is ack'd -> a beat passes while
		// the backend actually resumes the agent -> the resume's first event
		// lands -> the resumed turn finishes. The queued message must not
		// dispatch until that last step.
		store.currentSessionId = "s1";

		store.isStreaming = true;
		await store.sendMessage("QUEUED-ONE", [], null, "m1");
		expect(store.queuedMessages).toHaveLength(1);

		const essayMsg = {
			role: "assistant",
			message_id: "m-essay",
			blocks: [
				{
					type: "interaction",
					id: "call_1",
					status: "pending",
					interactionType: "approval",
					interrupts: [{ id: "int1" }],
				},
			],
		};
		store.messages = [...store.messages, essayMsg];
		store.hasPendingInteraction = true;
		store.completeStreaming("partial essay so far", {
			interrupted: true,
			blocks: essayMsg.blocks,
		});
		expect(store.isStreaming).toBe(false);
		expect(store.hasPendingInteraction).toBe(true);

		// Sanity: the queue correctly withholds during the pause itself.
		await nextTick();
		await flush();
		expect(api.chat.send).not.toHaveBeenCalled();

		// User clicks Approve; resume_interrupt is ack'd.
		await store.submitInterruptDecision({
			blockId: "call_1",
			resolution: "approved",
			userResponse: null,
			response: "approve",
		});
		expect(store.hasPendingInteraction).toBe(false);
		// The agent hasn't resumed yet — this is the transient window.
		expect(store.isStreaming).toBe(false);

		await nextTick();
		await flush();
		// THE BUG: the old code let hasPendingInteraction:false +
		// isStreaming:false (both true here) fire the dispatch right now,
		// before the resume produced anything.
		expect(api.chat.send).not.toHaveBeenCalled();

		// The resume stream's first event arrives.
		store.handleStreamResumed();
		expect(store.isStreaming).toBe(true);
		await nextTick();
		await flush();
		expect(api.chat.send).not.toHaveBeenCalled();

		// The resumed turn finishes.
		store.completeStreaming("Here's the essay, Paul…", {});
		expect(store.isStreaming).toBe(false);

		await nextTick();
		await flush();
		expect(api.chat.send).toHaveBeenCalledWith("s1", "QUEUED-ONE", [], null, "m1", null, [], {
			web_search: false,
			thinking_enabled: false,
		});
	});
});
