import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { setActivePinia, createPinia } from "pinia";
import InputArea from "./InputArea.vue";

describe("InputArea", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
	});

	it("fills textarea with initialMessage immediately on mount", async () => {
		const wrapper = mount(InputArea, {
			props: {
				isStreaming: false,
				interactionMode: null,
				context: null,
				initialMessage: "hi",
			},
		});
		await nextTick();
		const textarea = wrapper.find("textarea");
		expect(textarea.element.value).toBe("hi");
	});
});
