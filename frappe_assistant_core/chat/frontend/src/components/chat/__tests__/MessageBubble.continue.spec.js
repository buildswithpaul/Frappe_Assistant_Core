import { mount } from "@vue/test-utils";
import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import MessageBubble from "../MessageBubble.vue";

const truncatedMessage = {
	role: "assistant",
	message_id: "msg-1",
	content: "This answer got cut short",
	truncated: true,
	blocks: [{ type: "text", id: "b1", content: "This answer got cut short" }],
};

describe("MessageBubble Continue button", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
	});

	it("shows the Continue button when truncated and latest", () => {
		const wrapper = mount(MessageBubble, {
			props: { message: truncatedMessage, isLatest: true },
		});
		expect(wrapper.find(".continue-btn").exists()).toBe(true);
	});

	it("hides the Continue button when truncated but not the latest message", () => {
		const wrapper = mount(MessageBubble, {
			props: { message: truncatedMessage, isLatest: false },
		});
		expect(wrapper.find(".continue-btn").exists()).toBe(false);
	});

	it("hides the Continue button when latest but not truncated", () => {
		const wrapper = mount(MessageBubble, {
			props: {
				message: { ...truncatedMessage, truncated: false },
				isLatest: true,
			},
		});
		expect(wrapper.find(".continue-btn").exists()).toBe(false);
	});

	it("emits continue with the message_id on click", async () => {
		const wrapper = mount(MessageBubble, {
			props: { message: truncatedMessage, isLatest: true },
		});
		await wrapper.find(".continue-btn").trigger("click");
		expect(wrapper.emitted("continue")).toBeTruthy();
		expect(wrapper.emitted("continue")[0]).toEqual(["msg-1"]);
	});
});
