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

// The relay emits stream_status while it waits to re-open a stream AR refused as busy.
describe("busy_retrying stream status", () => {
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
		chatStore.currentSessionId = "s-busy";
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
		onStreamEvent({ session_id: "s-busy", event, ...data });
	}

	it("marks the bubble as busy-retrying and resets the activity timer", () => {
		const bubble = streamingBubble();
		const reset = vi.spyOn(chatStore, "resetActivityTimeout");

		emit("stream_status", { status: "busy_retrying", attempt: 1, retry_after: 5 });

		expect(bubble.busyRetrying).toBe(true);
		expect(reset).toHaveBeenCalled();
	});

	it("clears the flag once the stream starts", () => {
		const bubble = streamingBubble();
		emit("stream_status", { status: "busy_retrying", attempt: 1, retry_after: 5 });

		emit("stream_start", { message_id: "m-1" });

		expect(bubble.busyRetrying).toBe(false);
	});

	it("ignores an unknown status", () => {
		const bubble = streamingBubble();

		emit("stream_status", { status: "something_new" });

		expect(bubble.busyRetrying).toBe(false);
	});
});
