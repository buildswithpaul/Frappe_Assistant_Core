import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";
import ChatInterface from "@/components/chat/ChatInterface.vue";
import { retryTarget } from "./retryTurn";

vi.mock("@/api/client", () => ({
	api: {
		chat: {
			send: vi.fn().mockResolvedValue({}),
			getMessages: vi.fn().mockResolvedValue({ messages: [] }),
			getLiveTurn: vi.fn().mockResolvedValue(null),
			retryTurn: vi.fn().mockResolvedValue({ status: "processing", session_id: "s1" }),
		},
		documents: { get: vi.fn() },
	},
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

const user = { role: "user", name: "MSG-U1", content: "What is overdue?" };
// What a reload shows for a turn whose stream failed: the errored partial the relay persisted.
const errored = { role: "assistant", message_id: "m1", content: "Half an ans", errored: 1, blocks: [] };
// What mark_turn_interrupted leaves after a worker died mid-answer.
const interrupted = { ...errored, error_code: "TURN_INTERRUPTED" };
const complete = { role: "assistant", message_id: "m1", content: "Three are overdue.", blocks: [] };
const stopped = { ...complete, aborted: 1 };

describe("Retry", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
		store.currentSessionId = "s1";
		vi.clearAllMocks();
	});

	it("Retry shows on errored and interrupted turns only", () => {
		expect(retryTarget([user, errored])).toEqual({ index: 1, userMessage: "MSG-U1" });
		expect(retryTarget([user, interrupted])).toEqual({ index: 1, userMessage: "MSG-U1" });
		expect(retryTarget([user, complete])).toBeNull();
		expect(retryTarget([user, stopped])).toBeNull();
		expect(retryTarget([user, { ...errored, isStreaming: true }])).toBeNull();
		expect(retryTarget([{ ...user, name: undefined }, errored])).toBeNull();
		// Only the latest turn: an older errored answer stays as it is.
		expect(retryTarget([user, errored, { ...user, name: "MSG-U2" }, complete])).toBeNull();

		const wrapper = mount(ChatInterface, { props: { messages: [user, errored] } });
		expect(wrapper.findAll(".retry-btn")).toHaveLength(1);
		const done = mount(ChatInterface, { props: { messages: [user, complete] } });
		expect(done.find(".retry-btn").exists()).toBe(false);
	});

	it("emits the user message to retry", async () => {
		const wrapper = mount(ChatInterface, { props: { messages: [user, errored] } });
		await wrapper.find(".retry-btn").trigger("click");
		expect(wrapper.emitted("retry")[0]).toEqual(["MSG-U1"]);
	});

	it("Retry removes the partial bubble and streams into a new one", async () => {
		store.messages = [{ ...user }, { ...errored }];

		await store.retryTurn("MSG-U1");

		expect(api.chat.retryTurn).toHaveBeenCalledWith(
			"s1",
			"MSG-U1",
			expect.objectContaining({ client_turn_id: expect.any(String) })
		);
		expect(store.messages).toHaveLength(2);
		const bubble = store.messages[1];
		expect(bubble.role).toBe("assistant");
		expect(bubble.content).toBe("");
		expect(bubble.errored).toBeFalsy();
		expect(bubble.isStreaming).toBe(true);
		expect(store.isStreaming).toBe(true);
		expect(api.chat.retryTurn.mock.calls[0][2].client_turn_id).toBe(bubble._requestId);
	});

	it("already_complete reloads the conversation", async () => {
		store.messages = [{ ...user }, { ...errored }];
		api.chat.retryTurn.mockResolvedValueOnce({ status: "already_complete" });
		api.chat.getMessages.mockResolvedValueOnce({ messages: [{ ...user }, { ...complete }] });

		await store.retryTurn("MSG-U1");

		expect(api.chat.getMessages).toHaveBeenCalledWith("s1");
		expect(store.isStreaming).toBe(false);
		expect(store.messages.map((m) => m.content)).toEqual(["What is overdue?", "Three are overdue."]);
	});
});
