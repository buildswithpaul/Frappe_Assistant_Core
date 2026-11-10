import { mount } from "@vue/test-utils";
import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import MessageBubble from "../MessageBubble.vue";

// handleStreamError leaves this shape on the bubble when AR refuses a send for a low balance.
const refused = {
	role: "assistant",
	content: "",
	blocks: [],
	lowBalance: {
		estimate: 12.5,
		balance: 4,
		resend: { message: "Summarise the overdue invoices", files: [], context: null, modelId: "m1" },
	},
};

function bubble(message, isLatest = true) {
	return mount(MessageBubble, {
		props: { message, isLatest },
		global: { stubs: { MessageBlockRenderer: true, FacoRobot: true } },
	});
}

describe("MessageBubble low-balance preview", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
	});

	it("shows estimate, balance and Send anyway on a low-balance refusal", () => {
		const wrapper = bubble(refused);
		const notice = wrapper.find(".low-balance-notice");
		expect(notice.exists()).toBe(true);
		expect(notice.text()).toContain("This message may cost about 12.5 credits and you have 4 left.");
		expect(notice.find(".send-anyway-btn").text()).toBe("Send anyway");
	});

	it("emits send-anyway with the refused message", async () => {
		const wrapper = bubble(refused);
		await wrapper.find(".send-anyway-btn").trigger("click");
		expect(wrapper.emitted("send-anyway")[0]).toEqual([refused]);
	});

	it("offers no Send anyway once a later turn exists", () => {
		expect(bubble(refused, false).find(".send-anyway-btn").exists()).toBe(false);
	});

	it("shows nothing on an ordinary answer", () => {
		expect(bubble({ role: "assistant", content: "Hi", blocks: [] }).find(".low-balance-notice").exists()).toBe(
			false
		);
	});
});
