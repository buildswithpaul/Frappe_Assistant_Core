import { mount } from "@vue/test-utils";
import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import ChatInterface from "../ChatInterface.vue";
import MessageBlockRenderer from "../MessageBlockRenderer.vue";

const turn = (id) => ({
	role: "assistant",
	message_id: id,
	content: "",
	blocks: [{ type: "text", id: `${id}-t`, content: "answer" }],
});

describe("ChatInterface while an answered card's resume is in flight", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("holds only the latest assistant turn open", () => {
		const wrapper = mount(ChatInterface, {
			props: { messages: [turn("m1"), { role: "user", content: "next" }, turn("m2")], isResuming: true },
		});

		const flags = wrapper.findAllComponents(MessageBlockRenderer).map((r) => r.props("isResuming"));
		// One renderer per bubble, the user's included; only the last (m2) is resuming.
		expect(flags).toEqual([false, false, true]);
	});
});
