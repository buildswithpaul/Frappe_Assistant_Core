import { describe, it, expect, vi, beforeAll } from "vitest";
import { defineComponent } from "vue";
import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { useStreaming } from "@/composables/useStreaming";
import { useChatStore } from "@/stores/chatStore";

vi.mock("@/api/client", () => ({
	api: {
		chat: { getMessages: vi.fn().mockResolvedValue([]) },
		get: vi.fn().mockResolvedValue({}),
	},
}));

vi.mock("socket.io-client", () => {
	const fakeSocket = {
		connected: true,
		on: vi.fn(),
		off: vi.fn(),
		emit: vi.fn(),
		connect: vi.fn(),
		io: { on: vi.fn() },
	};
	return { io: vi.fn(() => fakeSocket), __fakeSocket: fakeSocket };
});
import * as socketIoMock from "socket.io-client";

/**
 * Which model answered is reported over three socket events, and the SPA was
 * deaf to all of them: it listened for "model_fallback" (a name the relay
 * never emits — it sends "model_selected") and the relay's stream_start /
 * stream_complete carried no model at all, so `meta.model_id` was always
 * undefined and every bubble rendered without its model.
 *
 * P3b1: the pick now lands as `message.routing` — the receipt every
 * disclosure level reads. The old `model_info` / `autoModeSelection` pair
 * had no production reader and is gone.
 */
describe("model reporting over the stream socket", () => {
	let chatStore;
	let onStreamEvent;

	beforeAll(() => {
		const pinia = createPinia();
		const Dummy = defineComponent({
			setup() {
				useStreaming();
				return () => null;
			},
		});
		mount(Dummy, { global: { plugins: [pinia] } });

		chatStore = useChatStore(pinia);
		chatStore.currentSessionId = "s-model";
		onStreamEvent = socketIoMock.__fakeSocket.on.mock.calls.find(
			(c) => c[0] === "faco_message_stream"
		)[1];
	});

	function streamingBubble() {
		chatStore.messages = [
			{ role: "user", content: "hi" },
			{ role: "assistant", content: "", blocks: [], isStreaming: true },
		];
		return chatStore.messages[1];
	}

	function emit(event, data = {}) {
		onStreamEvent({ session_id: "s-model", event, ...data });
	}

	it("attaches the live receipt to the streaming bubble", () => {
		const bubble = streamingBubble();

		emit("model_selected", {
			selected: "claude-haiku-4-5",
			tier: "Economy",
			routing: {
				v: 1,
				mode: "auto",
				incomplete: true,
				selected_model: "claude-haiku-4-5",
				selected_tier: "Economy",
				bound_by: "neither",
			},
		});

		expect(bubble.routing?.selected_model).toBe("claude-haiku-4-5");
		expect(bubble.routing?.incomplete).toBe(true);
	});

	it("leaves the bubble alone when the event carries no receipt", () => {
		// An explicit turn on an older AR still emits the event.
		const bubble = streamingBubble();

		emit("model_selected", { selected: "claude-haiku-4-5", tier: "Economy" });

		expect(bubble.routing).toBeFalsy();
	});

	it("no longer writes the retired model_info shape", () => {
		const bubble = streamingBubble();

		emit("model_selected", {
			selected: "claude-haiku-4-5",
			routing: { v: 1, mode: "auto", selected_model: "claude-haiku-4-5" },
		});

		expect(bubble.model_info).toBeUndefined();
	});

	it("pins the model at stream_start, before a single chunk arrives", () => {
		const bubble = streamingBubble();

		emit("stream_start", { message_id: "m-1", model_id: "claude-sonnet-4-6" });

		expect(bubble.model_id).toBe("claude-sonnet-4-6");
	});

	it("records the model the turn actually completed on", () => {
		const bubble = streamingBubble();

		emit("stream_complete", {
			full_response: "done",
			model_id: "claude-sonnet-4-6",
			credits_used: 3,
		});

		expect(bubble.model_id).toBe("claude-sonnet-4-6");
	});
});
