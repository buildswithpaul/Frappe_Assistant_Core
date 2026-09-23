import { mount } from "@vue/test-utils";
import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import MessageBubble from "../MessageBubble.vue";

describe("MessageBubble anchor", () => {
	beforeEach(() => setActivePinia(createPinia()));
	it("exposes data-turn-index from messageIndex", () => {
		const wrapper = mount(MessageBubble, {
			props: {
				message: { role: "user", content: "hello", blocks: [] },
				messageIndex: 7,
			},
		});
		expect(wrapper.attributes("data-turn-index")).toBe("7");
	});

	it("emits pin with the message_id when the pin button is clicked", async () => {
		const wrapper = mount(MessageBubble, {
			props: {
				message: { role: "assistant", message_id: "m-9", content: "hello", blocks: [] },
			},
		});
		await wrapper.find('.message-actions button[title="Pin to index"]').trigger("click");
		expect(wrapper.emitted("pin")[0]).toEqual(["m-9"]);
	});
});
