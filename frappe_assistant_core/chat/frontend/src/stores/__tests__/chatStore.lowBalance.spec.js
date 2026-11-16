import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: { chat: { send: vi.fn(), cancelStream: vi.fn() } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn() }));

// The relay's stream_error when AR refuses a new message for a low balance.
const REFUSAL = {
	error: "Your balance may not cover this message.",
	error_code: "low_balance",
	low_balance: { estimate: 12.5, balance: 4, scope: "tenant" },
	blocks: [],
	partial_response: "",
};
const FILE = { file_name: "invoices.txt", file_url: "/private/files/invoices.txt" };

describe("a low-balance refusal and Send anyway", () => {
	let store;

	beforeEach(async () => {
		setActivePinia(createPinia());
		localStorage.clear();
		vi.clearAllMocks();
		api.chat.send.mockResolvedValue({});
		store = useChatStore();
		store.currentSessionId = "s1";
		await store.sendMessage("Summarise the overdue invoices", [FILE], { doctype: "Sales Invoice" }, "m1");
		store.handleStreamError(REFUSAL.error, REFUSAL.error_code, REFUSAL);
	});

	it("keeps the refused bubble with its numbers instead of an error banner", () => {
		const refused = store.messages.at(-1);
		expect(refused.lowBalance).toMatchObject({
			estimate: 12.5,
			balance: 4,
			resend: { message: "Summarise the overdue invoices", files: [FILE], context: { doctype: "Sales Invoice" }, modelId: "m1" },
		});
		expect(refused.isStreaming).toBe(false);
		expect(store.error).toBeFalsy();
		expect(store.isStreaming).toBe(false);
	});

	it("Send anyway re-sends the same text with confirm_low_balance", async () => {
		await store.sendAnyway(store.messages.at(-1));

		expect(api.chat.send).toHaveBeenCalledTimes(2);
		const [, message, fileUrls, context, modelId, , , options] = api.chat.send.mock.calls[1];
		expect(message).toBe("Summarise the overdue invoices");
		expect(fileUrls).toEqual([FILE.file_url]);
		expect(context).toEqual({ doctype: "Sales Invoice" });
		expect(modelId).toBe("m1");
		expect(options.confirm_low_balance).toBe(1);
	});

	it("Send anyway is not queued, so the confirmation cannot be dropped", async () => {
		// The queue keeps only text, files, context and model. A send is queued while a turn
		// streams or a Stop's cancel is still in flight; the refused turn has already ended.
		store.isStreaming = true;
		await store.sendAnyway(store.messages.at(-1));

		expect(api.chat.send).toHaveBeenCalledTimes(2);
		expect(api.chat.send.mock.calls[1][7].confirm_low_balance).toBe(1);
	});

	it("Send anyway replaces the refused exchange rather than repeating it", async () => {
		await store.sendAnyway(store.messages.at(-1));

		expect(store.messages.map((m) => m.role)).toEqual(["user", "assistant"]);
		expect(store.messages.at(-1).lowBalance).toBeUndefined();
	});

	it("Send anyway reaches the view through the conversation", async () => {
		const { mount } = await import("@vue/test-utils");
		const ChatInterface = (await import("@/components/chat/ChatInterface.vue")).default;
		const wrapper = mount(ChatInterface, {
			props: { messages: store.messages },
			global: { stubs: { MessageBlockRenderer: true, FacoRobot: true } },
		});
		await wrapper.find(".send-anyway-btn").trigger("click");
		expect(wrapper.emitted("send-anyway")[0]).toEqual([store.messages.at(-1)]);
	});

	it("an ordinary send carries no confirmation", () => {
		expect(api.chat.send.mock.calls[0][7]).not.toHaveProperty("confirm_low_balance");
	});
});
