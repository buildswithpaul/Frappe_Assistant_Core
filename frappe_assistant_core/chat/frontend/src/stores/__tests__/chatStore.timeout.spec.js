import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "../chatStore";
import { api } from "@/api/client";
import { vi } from "vitest";

vi.mock("@/api/client", () => ({ api: { chat: { getMessages: vi.fn() } } }));

describe("chatStore.handleStreamTimeout block finalization", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		store = useChatStore();
	});

	it("finalizes running tool_call and streaming thinking blocks so no spinner is orphaned", () => {
		store.currentSessionId = "s1";
		store.isStreaming = true;
		store.messages.push({
			role: "assistant",
			message_id: "m1",
			isStreaming: true,
			content: "partial",
			blocks: [
				{ type: "thinking", id: "th1", content: "…", isStreaming: true },
				{ type: "text", id: "tx1", content: "partial" },
				{
					type: "tool_call",
					id: "t1",
					tool_name: "get_document",
					status: "running",
					result: null,
				},
			],
		});

		store.handleStreamTimeout("No response received for 3 minutes.");

		const msg = store.messages[0];
		expect(store.isStreaming).toBe(false);
		expect(msg.isStreaming).toBe(false);
		expect(msg.error).toBe(true);

		const tool = msg.blocks.find((b) => b.id === "t1");
		expect(tool.status).toBe("error");
		expect(tool.result.message).toMatch(/Timed out/);
		expect(tool.endTime).toBeTruthy();

		const thinking = msg.blocks.find((b) => b.id === "th1");
		expect(thinking.isStreaming).toBe(false);
	});

	it("leaves finished blocks untouched", () => {
		store.currentSessionId = "s1";
		store.isStreaming = true;
		store.messages.push({
			role: "assistant",
			message_id: "m1",
			isStreaming: true,
			content: "done part",
			blocks: [
				{
					type: "tool_call",
					id: "t1",
					tool_name: "get_document",
					status: "success",
					result: { ok: true },
					endTime: "2026-07-23T12:00:00.000Z",
				},
			],
		});

		store.handleStreamTimeout("No response received for 3 minutes.");

		const tool = store.messages[0].blocks[0];
		expect(tool.status).toBe("success");
		expect(tool.result).toEqual({ ok: true });
		expect(tool.endTime).toBe("2026-07-23T12:00:00.000Z");
	});
});

// Silence is "no events reached us", not "the turn failed" — the finalizer is
// fire-and-forget too. The watchdog must ask the server before blaming the
// connection, or it reports a timeout for a turn that actually succeeded.
describe("activity watchdog reconciles before declaring a timeout", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		store = useChatStore();
		vi.clearAllMocks();
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	function armLiveTurn() {
		store.currentSessionId = "s1";
		store.isStreaming = true;
		store.messages.push({
			role: "assistant",
			message_id: "m1",
			isStreaming: true,
			blocks: [],
		});
		store.resetActivityTimeout();
	}

	it("adopts the finished turn instead of erroring", async () => {
		armLiveTurn();
		api.chat.getMessages.mockResolvedValue([
			{
				role: "assistant",
				message_id: "m1",
				content: "answer",
				blocks: JSON.stringify([{ type: "text", id: "t1", content: "answer" }]),
			},
		]);

		await vi.advanceTimersByTimeAsync(180000);

		expect(store.messages[0].content).toBe("answer");
		expect(store.isStreaming).toBe(false);
		expect(store.error).toBeFalsy();
	});

	it("still reports the timeout when the turn really is stalled", async () => {
		armLiveTurn();
		// Server row is still the stream_start shell — nothing landed.
		api.chat.getMessages.mockResolvedValue([
			{ role: "assistant", message_id: "m1", content: "", blocks: null },
		]);

		await vi.advanceTimersByTimeAsync(180000);

		expect(store.isStreaming).toBe(false);
		expect(store.error).toMatch(/No response received/);
		expect(store.messages[0].error).toBe(true);
	});
});
