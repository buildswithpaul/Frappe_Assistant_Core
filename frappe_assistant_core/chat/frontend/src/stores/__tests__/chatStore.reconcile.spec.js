import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: { chat: { getMessages: vi.fn() } },
}));

describe("reconcileFromServer", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		store = useChatStore();
		vi.clearAllMocks();
	});

	it("restores finished task-rail blocks lost during a disconnect", async () => {
		store.currentSessionId = "s1";
		// Live UI froze with a stale in-progress plan block
		store.messages = [
			{ role: "user", content: "analyze" },
			{
				role: "assistant",
				message_id: "m1",
				isStreaming: false,
				blocks: [{ type: "plan", id: "p1", tasks: [{ label: "t", status: "in_progress" }] }],
			},
		];
		// Server persisted the completed plan
		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "analyze" },
			{
				role: "assistant",
				message_id: "m1",
				blocks: JSON.stringify([
					{ type: "plan", id: "p1", tasks: [{ label: "t", status: "done" }] },
				]),
			},
		]);

		await store.reconcileFromServer("s1");

		const plan = store.messages[1].blocks.find((b) => b.type === "plan");
		expect(plan.tasks[0].status).toBe("done");
	});

	it("does not duplicate the mid-stream bubble the server already persisted", async () => {
		store.currentSessionId = "s1";
		// The live bubble already has message_id "m2" (assigned on the first
		// stream_start) AND is still streaming. The server, via
		// _ensure_assistant_msg, persisted a row for that SAME message_id.
		// Mid-stream that row is the empty shell: the relay writes blocks only
		// at terminal boundaries (stream_complete / error / abort).
		store.messages = [
			{ role: "user", content: "hi" },
			{ role: "assistant", message_id: "m1", isStreaming: false, blocks: [] },
			{
				role: "assistant",
				message_id: "m2",
				isStreaming: true,
				blocks: [{ type: "text", id: "t9", content: "partial" }],
				_requestId: "req-live",
			},
		];
		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "hi" },
			{ role: "assistant", message_id: "m1", blocks: JSON.stringify([{ type: "text", id: "t1", content: "done" }]) },
			{ role: "assistant", message_id: "m2", content: "", blocks: null },
		]);

		await store.reconcileFromServer("s1");

		// Exactly one message carries message_id "m2".
		const m2s = store.messages.filter((m) => m.message_id === "m2");
		expect(m2s).toHaveLength(1);
		// It is the LIVE one — its partial block + _requestId survived, not the shell.
		expect(m2s[0].isStreaming).toBe(true);
		expect(m2s[0]._requestId).toBe("req-live");
		expect(m2s[0].blocks[0].content).toBe("partial");
		// No duplicate message_id anywhere in the list.
		const ids = store.messages.map((m) => m.message_id).filter(Boolean);
		expect(new Set(ids).size).toBe(ids.length);
		// Still exactly one actively-streaming bubble.
		const streaming = store.messages.filter((m) => m.isStreaming);
		expect(streaming).toHaveLength(1);
	});

	it("adopts the finished server row for a turn that completed during a disconnect", async () => {
		store.currentSessionId = "s1";
		store.isStreaming = true;
		store.messages = [
			{ role: "user", content: "hi" },
			{
				role: "assistant",
				message_id: "m1",
				isStreaming: true,
				blocks: [{ type: "text", id: "t9", content: "par" }],
				_requestId: "req-live",
			},
		];
		// stream_complete landed while the socket was down: the row is terminal.
		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "hi" },
			{
				role: "assistant",
				message_id: "m1",
				content: "the whole answer",
				blocks: JSON.stringify([{ type: "text", id: "t1", content: "the whole answer" }]),
			},
		]);

		await store.reconcileFromServer("s1");

		const m1s = store.messages.filter((m) => m.message_id === "m1");
		expect(m1s).toHaveLength(1);
		expect(m1s[0].content).toBe("the whole answer");
		expect(m1s[0].isStreaming).toBeFalsy();
		// The lock is released so the watchdog can't report a timeout for it.
		expect(store.isStreaming).toBe(false);
	});

	it("adopts an unmatched trailing row when the bubble never learned its message_id", async () => {
		store.currentSessionId = "s1";
		store.isStreaming = true;
		// Disconnected before stream_start, so no message_id was ever assigned.
		store.messages = [
			{ role: "user", content: "hi" },
			{ role: "assistant", isStreaming: true, blocks: [], _requestId: "req-live" },
		];
		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "hi" },
			{
				role: "assistant",
				message_id: "m1",
				content: "answer",
				blocks: JSON.stringify([{ type: "text", id: "t1", content: "answer" }]),
			},
		]);

		await store.reconcileFromServer("s1");

		const assistants = store.messages.filter((m) => m.role === "assistant");
		expect(assistants).toHaveLength(1);
		expect(assistants[0].content).toBe("answer");
		expect(store.isStreaming).toBe(false);
	});

	it("keeps a live continue turn whose server row is the pre-continue answer", async () => {
		store.currentSessionId = "s1";
		store.isStreaming = true;
		// A continue turn streams into the bubble of an already-finished answer,
		// so its terminal server row holds LESS than the user can already see.
		store.messages = [
			{ role: "user", content: "write an essay" },
			{
				role: "assistant",
				message_id: "m1",
				isStreaming: true,
				_continuing: true,
				content: "half an essay plus more",
				blocks: [{ type: "text", id: "t1", content: "half an essay plus more" }],
			},
		];
		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "write an essay" },
			{
				role: "assistant",
				message_id: "m1",
				content: "half an essay",
				blocks: JSON.stringify([{ type: "text", id: "t1", content: "half an essay" }]),
			},
		]);

		await store.reconcileFromServer("s1");

		const m1 = store.messages.find((m) => m.message_id === "m1");
		expect(m1.content).toBe("half an essay plus more");
		expect(m1.isStreaming).toBe(true);
		expect(store.isStreaming).toBe(true);
	});

	it("preserves the client-only truncated flag on a finished turn", async () => {
		store.currentSessionId = "s1";
		// A finished, max_tokens-truncated turn is in the persisted tail. Its
		// truncated flag drives the Continue button.
		store.messages = [
			{ role: "user", content: "write an essay" },
			{
				role: "assistant",
				message_id: "m1",
				isStreaming: false,
				truncated: true,
				blocks: [{ type: "text", id: "t1", content: "half an essay" }],
			},
		];
		// Server row for m1 does NOT carry the client-only truncated field.
		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "write an essay" },
			{ role: "assistant", message_id: "m1", blocks: JSON.stringify([{ type: "text", id: "t1", content: "half an essay" }]) },
		]);

		await store.reconcileFromServer("s1");

		const m1 = store.messages.find((m) => m.message_id === "m1");
		expect(m1.truncated).toBe(true);
	});

	it("replaces a locally timed-out bubble with the completed server row", async () => {
		store.currentSessionId = "s1";
		// The 180s watchdog fired mid-turn: bubble errored, no longer streaming.
		store.messages = [
			{ role: "user", content: "long analysis" },
			{
				role: "assistant",
				message_id: "m1",
				isStreaming: false,
				error: true,
				content: "partial",
				blocks: [{ type: "text", id: "t1", content: "partial" }],
			},
		];
		// The server finished the turn while the socket was down.
		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "long analysis" },
			{
				role: "assistant",
				message_id: "m1",
				content: "the complete answer",
				blocks: JSON.stringify([{ type: "text", id: "t1", content: "the complete answer" }]),
			},
		]);

		await store.reconcileFromServer("s1");

		const m1 = store.messages.find((m) => m.message_id === "m1");
		expect(m1.content).toBe("the complete answer");
		expect(m1.error).toBeUndefined();
	});

	it("keeps local partial content when the server row is still an empty shell", async () => {
		store.currentSessionId = "s1";
		// Timed out locally (not streaming any more) but the turn is STILL
		// running server-side — the persisted row is the stream_start shell.
		store.messages = [
			{ role: "user", content: "long analysis" },
			{
				role: "assistant",
				message_id: "m1",
				isStreaming: false,
				error: true,
				content: "partial the user can see",
				blocks: [{ type: "text", id: "t1", content: "partial the user can see" }],
			},
		];
		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "long analysis" },
			{ role: "assistant", message_id: "m1", content: "", blocks: null },
		]);

		await store.reconcileFromServer("s1");

		const m1 = store.messages.find((m) => m.message_id === "m1");
		expect(m1.content).toBe("partial the user can see");
		expect(m1.blocks[0].content).toBe("partial the user can see");
	});

	it("still surfaces server rows flagged errored/aborted even when empty", async () => {
		store.currentSessionId = "s1";
		store.messages = [
			{ role: "user", content: "q" },
			{
				role: "assistant",
				message_id: "m1",
				isStreaming: false,
				content: "local partial",
				blocks: [{ type: "text", id: "t1", content: "local partial" }],
			},
		];
		// An empty but TERMINAL server row is authoritative, not a shell.
		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "q" },
			{ role: "assistant", message_id: "m1", content: "", blocks: null, aborted: 1 },
		]);

		await store.reconcileFromServer("s1");

		const m1 = store.messages.find((m) => m.message_id === "m1");
		expect(m1.aborted).toBe(1);
		expect(m1.content).toBeFalsy();
	});

	it("handles the production {messages, has_more} shape with live bubble + truncated + shell guard at once", async () => {
		store.currentSessionId = "s1";
		store.messages = [
			{ role: "user", content: "q1" },
			// Truncated earlier turn (client-only flag drives Continue).
			{
				role: "assistant",
				message_id: "m1",
				isStreaming: false,
				truncated: true,
				content: "half",
				blocks: [{ type: "text", id: "t1", content: "half" }],
			},
			// Timed-out turn with partial content, server row still a shell.
			{
				role: "assistant",
				message_id: "m2",
				isStreaming: false,
				error: true,
				content: "partial",
				blocks: [{ type: "text", id: "t2", content: "partial" }],
			},
			// Live streaming bubble.
			{
				role: "assistant",
				message_id: "m3",
				isStreaming: true,
				blocks: [{ type: "text", id: "t3", content: "live" }],
				_requestId: "req-live",
			},
		];
		api.chat.getMessages.mockResolvedValue({
			messages: [
				{ role: "user", content: "q1" },
				{ role: "assistant", message_id: "m1", content: "half", blocks: JSON.stringify([{ type: "text", id: "t1", content: "half" }]) },
				{ role: "assistant", message_id: "m2", content: "", blocks: null },
				{ role: "assistant", message_id: "m3", content: "", blocks: null },
			],
			has_more: false,
		});

		await store.reconcileFromServer("s1");

		const m1 = store.messages.find((m) => m.message_id === "m1");
		expect(m1.truncated).toBe(true);
		const m2 = store.messages.find((m) => m.message_id === "m2");
		expect(m2.content).toBe("partial");
		const m3s = store.messages.filter((m) => m.message_id === "m3");
		expect(m3s).toHaveLength(1);
		expect(m3s[0].isStreaming).toBe(true);
		expect(m3s[0]._requestId).toBe("req-live");
	});

	it("no-ops when the session changed during the gap", async () => {
		store.currentSessionId = "s2";
		store.messages = [{ role: "user", content: "keep" }];
		await store.reconcileFromServer("s1");
		expect(api.chat.getMessages).not.toHaveBeenCalled();
		expect(store.messages).toHaveLength(1);
	});

	it("never flips the loading skeleton", async () => {
		store.currentSessionId = "s1";
		store.messages = [];
		api.chat.getMessages.mockResolvedValue([]);
		await store.reconcileFromServer("s1");
		expect(store.isLoading).toBe(false);
	});
});
