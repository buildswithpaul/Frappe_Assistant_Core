import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";
import { SILENCE_PROBE_MS, SILENCE_REPROBE_MS } from "./streamManager";

vi.mock("@/api/client", () => ({
	api: {
		chat: {
			send: vi.fn().mockResolvedValue({}),
			getMessages: vi.fn().mockResolvedValue({ messages: [] }),
			getLiveTurn: vi.fn().mockResolvedValue(null),
			markTurnInterrupted: vi.fn().mockResolvedValue({ interrupted: false }),
		},
	},
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

// A worker killed mid-turn takes its relay with it: no stream_complete or stream_error ever
// comes, and the live-turn entry stops being written (#34895).
describe("reconcile with a dead relay", () => {
	let store;
	const halfAnswer = [{ type: "text", id: "t1", content: "Half an ans" }];

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
		store.currentSessionId = "s1";
		vi.clearAllMocks();
		// This surface sent the turn and has streamed part of it.
		store.messages = [
			{ role: "user", content: "hello" },
			{ role: "assistant", message_id: "m1", content: "Half an ans", blocks: halfAnswer, isStreaming: true },
		];
		store.isStreaming = true;
	});

	it("a stale live turn is marked Interrupted on reconcile", async () => {
		api.chat.getLiveTurn.mockResolvedValue({ turn: "t-1", status: "streaming", message_id: "m1", stale: true });
		api.chat.markTurnInterrupted.mockResolvedValue({ interrupted: true, message_id: "m1" });
		api.chat.getMessages.mockResolvedValue({
			messages: [
				{ role: "user", content: "hello" },
				{ role: "assistant", message_id: "m1", content: "Half an ans", blocks: halfAnswer, errored: 1 },
			],
		});

		await store.reconcileFromServer("s1");

		expect(api.chat.markTurnInterrupted).toHaveBeenCalledWith("s1");
		expect(store.isStreaming).toBe(false);
		expect(store.errorCode).toBe("TURN_INTERRUPTED");
		expect(store.error).toBe("This answer was interrupted by a server restart.");
		const last = store.messages[store.messages.length - 1];
		expect(last.isStreaming).toBeFalsy();
		expect(last.errored).toBeTruthy();
		expect(store.messages.filter((m) => m.role === "assistant")).toHaveLength(1);
	});

	it("a fresh live turn keeps streaming", async () => {
		api.chat.getLiveTurn.mockResolvedValue({ turn: "t-1", status: "streaming", message_id: "m1", stale: false });
		// Mid-turn the server holds only the empty shell stream_start wrote.
		api.chat.getMessages.mockResolvedValue({
			messages: [
				{ role: "user", content: "hello" },
				{ role: "assistant", message_id: "m1", content: "", blocks: [] },
			],
		});

		await store.reconcileFromServer("s1");

		expect(api.chat.markTurnInterrupted).not.toHaveBeenCalled();
		expect(store.isStreaming).toBe(true);
		expect(store.messages[store.messages.length - 1].isStreaming).toBe(true);
		expect(store.error).toBeFalsy();
	});

	afterEach(() => vi.useRealTimers());

	it("a stale snapshot on join gets marked", async () => {
		// Opening the conversation after the worker died: the entry is stale, the row an empty shell.
		const stale = { turn: "t-1", seq: 4, status: "streaming", message_id: "m1", text: "Half an ans", stale: true };
		api.chat.getLiveTurn.mockResolvedValueOnce(stale).mockResolvedValueOnce(stale).mockResolvedValue(null);
		api.chat.markTurnInterrupted.mockResolvedValue({ interrupted: true, message_id: "m1" });
		const shell = [{ role: "user", content: "hello" }, { role: "assistant", message_id: "m1", content: "", blocks: [] }];
		const marked = [
			{ role: "user", content: "hello" },
			{ role: "assistant", message_id: "m1", content: "Half an ans", blocks: halfAnswer, errored: 1 },
		];
		api.chat.getMessages.mockResolvedValueOnce({ messages: shell }).mockResolvedValue({ messages: marked });
		store.isStreaming = false;

		await store.loadMessages("s1");
		await vi.waitFor(() => expect(store.messages[1]?.errored).toBeTruthy());

		expect(api.chat.markTurnInterrupted).toHaveBeenCalledWith("s1");
		expect(store.messages[1].content).toBe("Half an ans");
		expect(store.messages.some((m) => m.isStreaming)).toBe(false);
	});

	it("a silent stream gets probed", async () => {
		vi.useFakeTimers();
		// The relay's worker was SIGKILLed: the socket (another process) stays up, no events come.
		api.chat.getLiveTurn.mockResolvedValue({ turn: "t-1", status: "streaming", message_id: "m1", stale: true });
		api.chat.markTurnInterrupted.mockResolvedValue({ interrupted: true, message_id: "m1" });
		api.chat.getMessages.mockResolvedValue({
			messages: [
				{ role: "user", content: "hello" },
				{ role: "assistant", message_id: "m1", content: "Half an ans", blocks: halfAnswer, errored: 1 },
			],
		});
		store.resetActivityTimeout();

		await vi.advanceTimersByTimeAsync(SILENCE_PROBE_MS - 1000);
		expect(api.chat.getLiveTurn).not.toHaveBeenCalled();
		await vi.advanceTimersByTimeAsync(2000);

		expect(api.chat.markTurnInterrupted).toHaveBeenCalledWith("s1");
		expect(store.isStreaming).toBe(false);
		expect(store.errorCode).toBe("TURN_INTERRUPTED");
	});

	it("a live but quiet stream is probed again, not ended", async () => {
		vi.useFakeTimers();
		// A long tool call: AR heartbeats keep the entry fresh even when nothing reaches this tab.
		api.chat.getLiveTurn.mockResolvedValue({ turn: "t-1", status: "streaming", message_id: "m1", stale: false });
		store.resetActivityTimeout();

		await vi.advanceTimersByTimeAsync(SILENCE_PROBE_MS + 1000);
		expect(api.chat.getLiveTurn).toHaveBeenCalledTimes(1);
		// The entry goes stale 60 s after its last write, so a quiet turn is asked again soon.
		await vi.advanceTimersByTimeAsync(SILENCE_REPROBE_MS);

		expect(api.chat.getLiveTurn).toHaveBeenCalledTimes(2);
		expect(api.chat.markTurnInterrupted).not.toHaveBeenCalled();
		expect(store.isStreaming).toBe(true);
	});

	it("a stale snapshot is not adopted as a live bubble", async () => {
		store.messages = [{ role: "user", content: "hello" }];
		store.isStreaming = false;
		api.chat.getLiveTurn.mockResolvedValue({
			turn: "t-1",
			seq: 4,
			status: "streaming",
			message_id: "m1",
			text: "Half an ans",
			blocks: halfAnswer,
			stale: true,
		});

		await store.recoverLiveTurn("s1");

		expect(store.messages.some((m) => m.isStreaming)).toBe(false);
	});
});
