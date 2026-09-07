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

	it("handles the auto-mode pick under the name the relay emits", () => {
		const bubble = streamingBubble();

		emit("model_selected", { selected: "claude-haiku-4-5", tier: "Economy" });

		expect(chatStore.autoModeSelection?.selected).toBe("claude-haiku-4-5");
		expect(bubble.model_info).toMatchObject({
			model_id: "claude-haiku-4-5",
			auto_selected: true,
		});
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
