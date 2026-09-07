import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";

vi.mock("@/api/client", () => ({
	api: { chat: { getMessages: vi.fn(), cancelStream: vi.fn().mockResolvedValue({}) } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

function markerCount(blocks) {
	return blocks.filter((b) => b._abortMarker).length;
}

describe("handleStreamAborted abort-marker rendering", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		store = useChatStore();
	});

	it("renders exactly one marker when the server snapshot already carries it (abortPendingInteraction path)", () => {
		// Mirrors cancel.py's HITL-pause finalizer (_abort_pending_interactions):
		// it never goes through abortStream()'s optimistic local append, so the
		// local blocks arriving here have no marker — but the server's own
		// idempotent append_abort_marker already put one in `data.blocks`.
		store.messages = [
			{
				role: "assistant",
				message_id: "m1",
				isStreaming: true,
				blocks: [{ type: "text", id: "t1", content: "partial answer" }],
			},
		];

		store.handleStreamAborted({
			session_id: "s1",
			partial_response: "partial answer",
			blocks: [
				{ type: "text", id: "t1", content: "partial answer" },
				{
					type: "text",
					id: "abort-marker-server",
					content: "\n\n_(Stopped by user)_",
					_abortMarker: true,
				},
			],
		});

		const lastMsg = store.messages[store.messages.length - 1];
		expect(markerCount(lastMsg.blocks)).toBe(1);
	});

	it("still appends a marker when the server snapshot has none", () => {
		store.messages = [
			{
				role: "assistant",
				message_id: "m1",
				isStreaming: true,
				blocks: [{ type: "text", id: "t1", content: "partial answer" }],
			},
		];

		store.handleStreamAborted({
			session_id: "s1",
			partial_response: "partial answer",
			blocks: [{ type: "text", id: "t1", content: "partial answer" }],
		});

		const lastMsg = store.messages[store.messages.length - 1];
		expect(markerCount(lastMsg.blocks)).toBe(1);
	});
});
