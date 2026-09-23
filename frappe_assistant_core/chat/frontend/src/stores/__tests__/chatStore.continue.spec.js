import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "../chatStore";
import { useComposerModesStore } from "../composerModesStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: {
		chat: {
			continueResponse: vi.fn().mockResolvedValue({ success: true }),
		},
	},
}));

describe("chatStore.continueMessage", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		// composerModesStore hydrates from localStorage at construction; a leaked
		// entry from another spec would make the forwarded flags non-deterministic.
		localStorage.clear();
		vi.clearAllMocks();
	});

	it("seeds streamingMessage with the bubble's existing content, marks it streaming, and clears truncated", async () => {
		const store = useChatStore();
		store.currentSessionId = "session-1";
		store.messages.push({
			role: "assistant",
			message_id: "msg-1",
			content: "Here is the start of a long answer that got cut",
			truncated: true,
			isStreaming: false,
			blocks: [
				{
					type: "text",
					id: "b1",
					content: "Here is the start of a long answer that got cut",
				},
			],
		});

		await store.continueMessage("msg-1");

		expect(store.streamingMessage).toBe(
			"Here is the start of a long answer that got cut"
		);
		const bubble = store.messages[store.messages.length - 1];
		expect(bubble.isStreaming).toBe(true);
		expect(bubble.truncated).toBe(false);
		expect(store.isStreaming).toBe(true);
	});

	it("calls continueResponse with (sessionId, messageId) and pushes no user message", async () => {
		const store = useChatStore();
		store.currentSessionId = "session-42";
		store.messages.push({
			role: "assistant",
			message_id: "msg-42",
			content: "partial",
			truncated: true,
			isStreaming: false,
			blocks: [],
		});
		const lengthBefore = store.messages.length;

		await store.continueMessage("msg-42");

		expect(api.chat.continueResponse).toHaveBeenCalledWith("session-42", "msg-42", {
			web_search: false,
			thinking_enabled: false,
		});
		expect(store.messages.length).toBe(lengthBefore);
		expect(store.messages.every((m) => m.role !== "user")).toBe(true);
	});

	it("carries the conversation's composer toggles into the continuation", async () => {
		// A continuation that forwards nothing reaches AR as absence, and AR
		// reads absence as "search available" — so a turn the user marked
		// search-off would finish with search silently back on.
		const modes = useComposerModesStore();
		modes.toggle("session-42", "webSearch");
		modes.toggle("session-42", "thinking");
		modes.toggle("session-42", "webSearch"); // back off — the state the pill shows

		const store = useChatStore();
		store.currentSessionId = "session-42";
		store.messages.push({
			role: "assistant",
			message_id: "msg-42",
			content: "partial",
			truncated: true,
			isStreaming: false,
			blocks: [],
		});

		await store.continueMessage("msg-42");

		expect(api.chat.continueResponse).toHaveBeenCalledWith("session-42", "msg-42", {
			web_search: false,
			thinking_enabled: true,
		});
	});

	it("is a no-op when the message_id does not belong to the latest assistant message", async () => {
		const store = useChatStore();
		store.currentSessionId = "session-1";
		store.messages.push(
			{
				role: "assistant",
				message_id: "msg-old",
				content: "old truncated answer",
				truncated: true,
				isStreaming: false,
				blocks: [],
			},
			{
				role: "user",
				content: "another question",
			},
			{
				role: "assistant",
				message_id: "msg-new",
				content: "fresh answer",
				truncated: false,
				isStreaming: false,
				blocks: [],
			}
		);

		await store.continueMessage("msg-old");

		expect(api.chat.continueResponse).not.toHaveBeenCalled();
		expect(store.isStreaming).toBe(false);
		const stale = store.messages.find((m) => m.message_id === "msg-old");
		expect(stale.isStreaming).toBe(false);
	});

	it("appended stream chunks concatenate onto the existing content, not replace it", async () => {
		const store = useChatStore();
		store.currentSessionId = "session-1";
		store.messages.push({
			role: "assistant",
			message_id: "msg-1",
			content: "Once upon a time",
			truncated: true,
			isStreaming: false,
			blocks: [{ type: "text", id: "b1", content: "Once upon a time" }],
		});

		await store.continueMessage("msg-1");
		store.appendStreamChunk(", there was a king.");

		const bubble = store.messages[store.messages.length - 1];
		expect(bubble.content).toBe("Once upon a time, there was a king.");
		expect(store.streamingMessage).toBe("Once upon a time, there was a king.");
	});

	it("stream_complete's combined full_response overwrites content exactly once (no doubling)", async () => {
		const store = useChatStore();
		store.currentSessionId = "session-1";
		store.messages.push({
			role: "assistant",
			message_id: "msg-1",
			content: "Once upon a time",
			truncated: true,
			isStreaming: false,
			blocks: [{ type: "text", id: "b1", content: "Once upon a time" }],
		});

		await store.continueMessage("msg-1");
		store.appendStreamChunk(", there was a king.");

		const combined = "Once upon a time, there was a king. The end.";
		store.completeStreaming(combined, { blocks: [{ type: "text", id: "b1", content: combined }] });

		const bubble = store.messages[store.messages.length - 1];
		expect(bubble.content).toBe(combined);
		expect(bubble.content.indexOf("Once upon a time")).toBe(
			bubble.content.lastIndexOf("Once upon a time")
		);
	});

	it("restores the truncated affordance when the continue request throws immediately", async () => {
		api.chat.continueResponse.mockRejectedValueOnce(new Error("network down"));
		const store = useChatStore();
		store.currentSessionId = "session-1";
		store.messages.push({
			role: "assistant",
			message_id: "msg-1",
			content: "Half an answer",
			truncated: true,
			isStreaming: false,
			blocks: [{ type: "text", id: "b1", content: "Half an answer" }],
		});

		await store.continueMessage("msg-1");

		const bubble = store.messages[store.messages.length - 1];
		// A failed continue must leave the answer continuable, not stranded.
		expect(bubble.truncated).toBe(true);
		expect(bubble.isStreaming).toBe(false);
		expect(bubble._continuing).toBe(false);
	});

	it("restores the truncated affordance (no error marker) when a continue stream_error arrives mid-flight", async () => {
		const store = useChatStore();
		store.currentSessionId = "session-1";
		store.messages.push({
			role: "assistant",
			message_id: "msg-1",
			content: "Half an answer",
			truncated: true,
			isStreaming: false,
			blocks: [{ type: "text", id: "b1", content: "Half an answer" }],
		});

		await store.continueMessage("msg-1");
		// The relay/socket delivers a stream_error for the continue turn.
		store.handleStreamError("stream failed", "STREAM_ERROR", {});

		const bubble = store.messages[store.messages.length - 1];
		expect(bubble.truncated).toBe(true);
		expect(bubble.errored).not.toBe(true);
		expect(bubble._continuing).toBe(false);
		// No "(Interrupted by an error)" marker was appended.
		expect((bubble.blocks || []).some((b) => b._errorMarker)).toBe(false);
	});

	it("restores the truncated affordance when a continue turn TIMES OUT (no events)", async () => {
		const store = useChatStore();
		store.currentSessionId = "session-1";
		store.messages.push({
			role: "assistant",
			message_id: "msg-1",
			content: "Half an answer",
			truncated: true,
			isStreaming: false,
			blocks: [{ type: "text", id: "b1", content: "Half an answer" }],
		});

		await store.continueMessage("msg-1");
		// The activity timer fires with no SSE event ever arriving — this is the
		// distinct handleStreamTimeout path (NOT handleStreamError).
		store.handleStreamTimeout("No response received for 3 minutes.");

		const bubble = store.messages[store.messages.length - 1];
		expect(bubble.truncated).toBe(true);
		expect(bubble.error).not.toBe(true);
		expect(bubble._continuing).toBe(false);
	});
});
