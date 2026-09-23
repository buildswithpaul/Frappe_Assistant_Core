import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";

// Live-bug repro (e2e-5): user sends a prompt, the assistant starts
// streaming, the user queues a second message mid-stream — that push
// dropped a "role: user, queued: true" bubble onto the END of `messages`.
// Every stream-event handler located "the active turn" via
// `messages[messages.length - 1]`, so once the queued bubble trailed the
// streaming assistant message, subsequent stream_chunk events could no
// longer find it: the visible answer froze mid-sentence while the relay
// kept persisting server-side (it keys by message_id, not array position).
vi.mock("@/api/client", () => ({
	api: {
		chat: {
			send: vi.fn().mockResolvedValue({}),
			cancelStream: vi.fn().mockResolvedValue({}),
		},
	},
}));

describe("streaming through a trailing queued bubble", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
		store.currentSessionId = "s1";
		vi.clearAllMocks();
	});

	it("keeps routing stream_chunk events to the assistant bubble after a message queues behind it", async () => {
		await store.sendMessage("Tell me about ancient history", [], null, "m1");
		expect(store.messages).toHaveLength(2); // user + streaming assistant

		store.appendStreamChunk("The Sumerians and Baby");

		// A second message typed mid-stream queues instead of sending, and its
		// bubble is appended AFTER the still-streaming assistant message.
		await store.sendMessage("what about egypt", [], null, "m1");
		expect(store.queuedMessages).toHaveLength(1);
		expect(store.messages).toHaveLength(3);
		expect(store.messages[2]).toMatchObject({ role: "user", queued: true });

		store.appendStreamChunk("lonians built early cities.");

		// No phantom bubble — still exactly one assistant message, and it
		// received both chunks.
		const assistantMsgs = store.messages.filter((m) => m.role === "assistant");
		expect(assistantMsgs).toHaveLength(1);
		expect(assistantMsgs[0].content).toBe(
			"The Sumerians and Babylonians built early cities."
		);
		expect(assistantMsgs[0].isStreaming).toBe(true);
	});

	it("marks the streaming assistant bubble (not the queued one) when Stop is pressed", async () => {
		await store.sendMessage("Explain quantum computing", [], null, "m1");
		store.appendStreamChunk("Quantum computers use qu");
		await store.sendMessage("also explain relativity", [], null, "m1");
		expect(store.messages).toHaveLength(3);

		// Capture references before awaiting: abortStream's own mutations are
		// synchronous, but awaiting it lets the send-queue's watcher dispatch
		// the now-unblocked queued message, which would otherwise remove its
		// bubble from `messages` out from under a post-await `.find()`.
		const assistantMsg = store.messages.find((m) => m.role === "assistant");
		const queuedMsg = store.messages.find((m) => m.queued);

		await store.abortStream();

		expect(assistantMsg.isStreaming).toBe(false);
		expect(assistantMsg.aborted).toBe(true);
		expect(assistantMsg.content).toContain("Quantum computers use qu");
		expect(assistantMsg.content).toContain("(Stopped by user)");

		expect(queuedMsg.aborted).toBeUndefined();
		expect(queuedMsg.isStreaming).toBeUndefined();
	});

	it("marks the streaming assistant bubble (not the queued one) when the activity timeout fires", async () => {
		await store.sendMessage("Write a long report", [], null, "m1");
		store.appendStreamChunk("Section one begins");
		await store.sendMessage("also add a summary", [], null, "m1");
		expect(store.messages).toHaveLength(3);

		store.handleStreamTimeout("No response received for 3 minutes.");

		const assistantMsg = store.messages.find((m) => m.role === "assistant");
		const queuedMsg = store.messages.find((m) => m.queued);

		expect(assistantMsg.isStreaming).toBe(false);
		expect(assistantMsg.error).toBe(true);
		expect(queuedMsg.error).toBeUndefined();
		expect(queuedMsg.isStreaming).toBeUndefined();
	});
});
