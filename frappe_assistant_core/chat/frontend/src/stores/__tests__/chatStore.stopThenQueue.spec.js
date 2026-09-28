import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { nextTick } from "vue";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { CANCEL_HOLD_MS } from "@/stores/chat/streamManager";
import { api } from "@/api/client";

// Stop turns isStreaming off at once, but FAC clears a session's
// cancel flag when it accepts a turn. A next message accepted just
// before the Stop reached FAC was stopped too; one accepted just after it
// cleared the flag before the stopped turn's relay had read it. The next
// message therefore waits until the Stop's cancel_stream has been answered.
vi.mock("@/api/client", () => ({
	api: { chat: { send: vi.fn(), cancelStream: vi.fn() } },
}));

// Lets the queue watcher's deferred (Promise.resolve().then) dispatch chain settle.
const flush = () => new Promise((r) => setTimeout(r, 0));

const FIRST = "Summarise the overdue invoices";
const NEXT = "Only the ones over 30 days";

describe("a Stop, then the next message", () => {
	let store, wire, cancels;

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		vi.clearAllMocks();
		// What reaches the server, in order. Each cancel stays unanswered until
		// the test answers it: cancels[i]() resolves it, cancels[i](false) fails it.
		wire = [];
		cancels = [];
		api.chat.send.mockImplementation(async (_sessionId, message) => {
			wire.push(`send_message: ${message}`);
			return {};
		});
		api.chat.cancelStream.mockImplementation(
			() =>
				new Promise((resolve, reject) => {
					wire.push("cancel_stream sent");
					cancels.push((ok = true) => {
						wire.push("cancel_stream answered");
						if (ok) resolve({});
						else reject(new Error("network down"));
					});
				})
		);
		store = useChatStore();
		store.currentSessionId = "s1";
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	async function answerStreamingWithAQueuedMessage() {
		await store.sendMessage(FIRST, [], null, "m1");
		store.appendStreamChunk("Three invoices are over");
		await store.sendMessage(NEXT, [], null, "m1");
		expect(store.queuedMessages).toHaveLength(1);
	}

	it("sends a queued message only once the Stop's cancel_stream is answered", async () => {
		await answerStreamingWithAQueuedMessage();

		const stopping = store.abortStream();
		await nextTick();
		await flush();
		cancels[0]();
		await stopping;
		await nextTick();
		await flush();

		expect(wire).toEqual([
			`send_message: ${FIRST}`,
			"cancel_stream sent",
			"cancel_stream answered",
			`send_message: ${NEXT}`,
		]);
	});

	it("queues a message sent right after Stop until the cancel is answered", async () => {
		await store.sendMessage(FIRST, [], null, "m1");
		const stopping = store.abortStream();

		// The Stop button is gone, so the composer routes this as a plain send.
		await store.sendMessage(NEXT, [], null, "m1");

		expect(store.queuedMessages).toHaveLength(1);
		cancels[0]();
		await stopping;
		await nextTick();
		await flush();
		expect(wire).toEqual([
			`send_message: ${FIRST}`,
			"cancel_stream sent",
			"cancel_stream answered",
			`send_message: ${NEXT}`,
		]);
		expect(store.queuedMessages).toHaveLength(0);
	});

	it("releases the queue when the cancel fails", async () => {
		await answerStreamingWithAQueuedMessage();

		const stopping = store.abortStream();
		cancels[0](false);
		await stopping;
		await nextTick();
		await flush();

		expect(wire).toEqual([
			`send_message: ${FIRST}`,
			"cancel_stream sent",
			"cancel_stream answered",
			`send_message: ${NEXT}`,
		]);
	});

	it("holds the queue until every Stop's cancel is answered", async () => {
		await answerStreamingWithAQueuedMessage();
		const firstStop = store.abortStream();
		// The abort-then-send route sends a fresh turn past the queue, and that
		// turn is stopped too, before the first cancel is answered.
		await store.sendMessage("Draft the reminder instead", [], null, "m1", null, {
			skipQueue: true,
		});
		const secondStop = store.abortStream();

		cancels[0]();
		await firstStop;
		await nextTick();
		await flush();
		expect(wire).not.toContain(`send_message: ${NEXT}`);

		cancels[1]();
		await secondStop;
		await nextTick();
		await flush();
		expect(wire.at(-1)).toBe(`send_message: ${NEXT}`);
	});

	it("holds the queue for CANCEL_HOLD_MS at most when no answer comes", async () => {
		vi.useFakeTimers();
		await answerStreamingWithAQueuedMessage();

		store.abortStream();
		await vi.advanceTimersByTimeAsync(CANCEL_HOLD_MS - 1);
		expect(wire).not.toContain(`send_message: ${NEXT}`);

		await vi.advanceTimersByTimeAsync(1);
		expect(wire).toEqual([
			`send_message: ${FIRST}`,
			"cancel_stream sent",
			`send_message: ${NEXT}`,
		]);
	});
});
