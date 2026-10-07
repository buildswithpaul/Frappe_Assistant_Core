import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: { chat: { getMessages: vi.fn(), getLiveTurn: vi.fn() }, get: vi.fn() },
}));

const history = [
	{ role: "user", content: "Count the orders" },
	{ role: "assistant", message_id: "m1", content: "", blocks: null },
];
const snapshot = {
	turn: "T1", seq: 4, message_id: "m1", status: "streaming", text: "There are ",
	blocks: [
		{ type: "thinking", id: "th1", content: "Counting", isStreaming: true },
		{ type: "tool_call", id: "toolu_1", tool_name: "get_count", status: "running" },
		{ type: "text", id: "tx1", content: "There are " },
	],
	active_thinking_id: null,
};

describe("joining a running turn", () => {
	let store;
	let handled;
	beforeEach(() => {
		setActivePinia(createPinia());
		store = useChatStore();
		vi.clearAllMocks();
		handled = [];
		store.setStreamDispatcher((e) => {
			handled.push(e);
			if (e.event === "stream_chunk") store.appendStreamChunk(e.chunk);
		});
		api.chat.getMessages.mockResolvedValue(history.map((m) => ({ ...m })));
	});

	it("shows the turn so far as a live answer", async () => {
		api.chat.getLiveTurn.mockResolvedValue(snapshot);
		await store.loadMessages("s1");
		const answer = store.messages[1];
		expect(answer.blocks.map((b) => b.type)).toEqual(["thinking", "tool_call", "text"]);
		expect(answer.isStreaming).toBe(true);
		expect(store.isStreaming).toBe(true);
	});

	it("keeps streaming onto the joined answer", async () => {
		api.chat.getLiveTurn.mockResolvedValue(snapshot);
		await store.loadMessages("s1");
		store.admitStreamEvent({ event: "stream_chunk", session_id: "s1", turn: "T1", seq: 5, chunk: "12." }) &&
			store.appendStreamChunk("12.");
		expect(store.messages[1].content).toBe("There are 12.");
		expect(store.messages[1].blocks.at(-1).content).toBe("There are 12.");
	});

	it("applies events held during the join only when newer than the snapshot", async () => {
		let resolveTurn;
		api.chat.getLiveTurn.mockReturnValue(new Promise((r) => (resolveTurn = r)));
		const loading = store.loadMessages("s1");
		expect(store.admitStreamEvent({ event: "stream_chunk", turn: "T1", seq: 4, chunk: "old" })).toBe(false);
		expect(store.admitStreamEvent({ event: "stream_chunk", turn: "T1", seq: 5, chunk: "12." })).toBe(false);
		resolveTurn(snapshot);
		await loading;
		expect(handled.map((e) => e.seq)).toEqual([5]);
		expect(store.messages[1].content).toBe("There are 12.");
	});

	it("leaves a finished conversation as it was", async () => {
		api.chat.getLiveTurn.mockResolvedValue(null);
		await store.loadMessages("s1");
		expect(store.isStreaming).toBe(false);
		expect(store.messages).toHaveLength(2);
	});

	it("restores the open thinking block so the next thought extends it", async () => {
		api.chat.getLiveTurn.mockResolvedValue({ ...snapshot, active_thinking_id: "th1" });
		await store.loadMessages("s1");
		expect(store.activeThinkingBlockId).toBe("th1");
	});

	it("drops a join when the conversation changes mid-read", async () => {
		let resolveTurn;
		api.chat.getLiveTurn.mockReturnValueOnce(new Promise((r) => (resolveTurn = r)));
		const first = store.loadMessages("s1");
		api.chat.getLiveTurn.mockResolvedValueOnce(null);
		api.chat.getMessages.mockResolvedValueOnce([{ role: "user", content: "other" }]);
		await store.loadMessages("s2");
		resolveTurn(snapshot);
		await first;
		expect(store.currentSessionId).toBe("s2");
		expect(store.messages).toHaveLength(1);
		expect(store.isStreaming).toBe(false);
	});

	it("rejoins from the snapshot on recovery, and reconciles when the turn has ended", async () => {
		api.chat.getLiveTurn.mockResolvedValue(snapshot);
		await store.loadMessages("s1");
		api.chat.getLiveTurn.mockResolvedValue({ ...snapshot, seq: 9, text: "There are 12 orders." });
		await store.recoverLiveTurn("s1");
		expect(store.messages[1].content).toBe("There are 12 orders.");
		// Recovery reconciles with the server whether or not a turn is still running.
		expect(api.chat.getMessages).toHaveBeenCalledTimes(2);

		api.chat.getLiveTurn.mockResolvedValue(null);
		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "Count the orders" },
			{ role: "assistant", message_id: "m1", content: "There are 12 orders.", blocks: "[]" },
		]);
		await store.recoverLiveTurn("s1");
		expect(api.chat.getMessages).toHaveBeenCalledTimes(3);
	});

	// Production: this tab's socket drops during T1, T1 finishes, the user sends T2
	// from the other surface, and this tab (isStreaming still true) comes back.
	it("does not overwrite a finished turn's answer when recovery finds a different turn running", async () => {
		api.chat.getLiveTurn.mockResolvedValue(snapshot);
		await store.loadMessages("s1");
		expect(store.messages[1].message_id).toBe("m1");

		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "Count the orders" },
			{ role: "assistant", message_id: "m1", content: "There are 12 orders.", blocks: "[]" },
			{ role: "user", content: "And the invoices?" },
		]);
		api.chat.getLiveTurn.mockResolvedValue({
			...snapshot, turn: "T2", message_id: "m2", seq: 2, text: "Invoices: ", blocks: [{ type: "text", id: "i1", content: "Invoices: " }],
		});
		await store.recoverLiveTurn("s1");

		const first = store.messages.find((m) => m.message_id === "m1");
		expect(first.content).toBe("There are 12 orders.");
		expect(store.messages.some((m) => m.role === "user" && m.content === "And the invoices?")).toBe(true);
		const last = store.messages.at(-1);
		expect(last.message_id).toBe("m2");
		expect(last.content).toBe("Invoices: ");
	});

	// Production reaches this when the user sends from the other surface: this
	// surface is idle on the session and receives numbered events for a turn it
	// never started.
	it("joins a turn begun on another surface and loads its question", async () => {
		api.chat.getLiveTurn.mockResolvedValueOnce(null);
		await store.loadMessages("s1");
		expect(api.chat.getMessages).toHaveBeenCalledTimes(1);

		api.chat.getLiveTurn.mockResolvedValue({ ...snapshot, turn: "T9", seq: 3 });
		const admitted = store.admitStreamEvent({
			event: "stream_chunk", session_id: "s1", turn: "T9", seq: 3, chunk: "x",
		});
		expect(admitted).toBe(false);
		await vi.waitFor(() => expect(store.isStreaming).toBe(true));
		expect(api.chat.getMessages).toHaveBeenCalledTimes(2);
		const last = store.messages.at(-1);
		expect(last.role).toBe("assistant");
		expect(last.isStreaming).toBe(true);
	});
});
