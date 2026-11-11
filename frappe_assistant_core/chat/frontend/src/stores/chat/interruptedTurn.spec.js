import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

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
