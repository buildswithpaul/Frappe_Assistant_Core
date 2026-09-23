import { mount } from "@vue/test-utils";
import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import MessageBubble from "../MessageBubble.vue";

const queuedMessage = {
	role: "user",
	content: "later please",
	queued: true,
	_queueId: "q1",
};

describe("MessageBubble queued chip", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
	});

	it("shows the Queued chip on a queued message", () => {
		const wrapper = mount(MessageBubble, { props: { message: queuedMessage } });
		expect(wrapper.find(".queued-chip").exists()).toBe(true);
	});

	it("hides the Queued chip on a normal message", () => {
		const wrapper = mount(MessageBubble, {
			props: { message: { role: "user", content: "hi" } },
		});
		expect(wrapper.find(".queued-chip").exists()).toBe(false);
	});

	it("emits unqueue with the message's queue id on click", async () => {
		const wrapper = mount(MessageBubble, { props: { message: queuedMessage } });
		await wrapper.find(".queued-remove").trigger("click");
		expect(wrapper.emitted("unqueue")).toBeTruthy();
		expect(wrapper.emitted("unqueue")[0]).toEqual(["q1"]);
	});
});
