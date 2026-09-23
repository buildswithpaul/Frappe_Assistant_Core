import { describe, it, expect, vi, beforeEach } from "vitest";
import { ref, nextTick } from "vue";
import { createSendQueue } from "./sendQueue";

// Let the watcher's deferred dispatch chain settle.
const flush = () => new Promise((r) => setTimeout(r, 0));

describe("createSendQueue", () => {
	let refs, sent, queue;

	beforeEach(() => {
		sent = [];
		refs = {
			messages: ref([]),
			currentSessionId: ref("s1"),
			isStreaming: ref(true),
			hasPendingInteraction: ref(false),
			isSubmittingInterrupts: ref(false),
			dispatch: vi.fn(async (item) => sent.push(item.message)),
		};
		queue = createSendQueue(refs);
	});

	it("queues an item and renders a queued bubble", () => {
		queue.queueMessage("later please", [], null, "m1");
		expect(queue.queuedMessages.value).toHaveLength(1);
		const bubble = refs.messages.value.find((m) => m._queueId);
		expect(bubble.queued).toBe(true);
		expect(bubble.content).toBe("later please");
		expect(bubble.role).toBe("user");
	});

	it("unqueue removes both the item and its bubble", () => {
		queue.queueMessage("oops", [], null, "m1");
		const id = queue.queuedMessages.value[0].id;
		queue.unqueueMessage(id);
		expect(queue.queuedMessages.value).toHaveLength(0);
		expect(refs.messages.value.find((m) => m._queueId === id)).toBeUndefined();
	});

	it("dispatches when streaming ends", async () => {
		queue.queueMessage("queued one", [], null, "m1");
		refs.isStreaming.value = false;
		await nextTick();
		await flush();
		expect(sent).toEqual(["queued one"]);
		expect(refs.messages.value.find((m) => m._queueId)).toBeUndefined();
	});

	it("dispatches items one at a time, in order", async () => {
		queue.queueMessage("first", [], null, "m1");
		queue.queueMessage("second", [], null, "m1");
		refs.isStreaming.value = false;
		await nextTick();
		await flush();
		// Only the head goes out; the next one waits for the following
		// finalization so two turns never race.
		expect(sent).toEqual(["first"]);
		expect(queue.queuedMessages.value).toHaveLength(1);
		expect(queue.queuedMessages.value[0].message).toBe("second");
	});

	it("does not dispatch while an interaction is pending", async () => {
		queue.queueMessage("wait for card", [], null, "m1");
		refs.hasPendingInteraction.value = true;
		refs.isStreaming.value = false;
		await nextTick();
		await flush();
		expect(sent).toEqual([]);
		expect(queue.queuedMessages.value).toHaveLength(1);
	});

	it("dispatches after the pending card resolves", async () => {
		queue.queueMessage("after card", [], null, "m1");
		refs.hasPendingInteraction.value = true;
		refs.isStreaming.value = false;
		await nextTick();
		await flush();
		refs.hasPendingInteraction.value = false;
		await nextTick();
		await flush();
		expect(sent).toEqual(["after card"]);
	});

	it("does not dispatch while a HITL resume is in flight (approval submitted but not yet resumed)", async () => {
		// Mirrors the real transient window: an approval's resume_interrupt
		// call has been ack'd (hasPendingInteraction already false) but the
		// resumed turn hasn't produced its first event yet (isStreaming still
		// false too). isSubmittingInterrupts is the only thing still gating.
		queue.queueMessage("after resume", [], null, "m1");
		refs.isStreaming.value = false;
		refs.isSubmittingInterrupts.value = true;
		await nextTick();
		await flush();
		expect(sent).toEqual([]);
		expect(queue.queuedMessages.value).toHaveLength(1);
	});

	it("dispatches once the resume is no longer in flight", async () => {
		queue.queueMessage("after resume", [], null, "m1");
		refs.isStreaming.value = false;
		refs.isSubmittingInterrupts.value = true;
		await nextTick();
		await flush();
		refs.isSubmittingInterrupts.value = false;
		await nextTick();
		await flush();
		expect(sent).toEqual(["after resume"]);
	});

	it("drops queue items belonging to a session the user left", async () => {
		queue.queueMessage("from s1", [], null, "m1");
		refs.currentSessionId.value = "s2";
		refs.isStreaming.value = false;
		await nextTick();
		await flush();
		expect(sent).toEqual([]);
		expect(queue.queuedMessages.value).toHaveLength(0);
		expect(refs.messages.value.find((m) => m._queueId)).toBeUndefined();
	});
});
