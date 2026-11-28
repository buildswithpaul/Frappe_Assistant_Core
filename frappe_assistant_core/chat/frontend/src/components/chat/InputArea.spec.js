import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { setActivePinia, createPinia } from "pinia";
import InputArea from "./InputArea.vue";
import { useApprovalModeStore } from "@/stores/approvalModeStore";

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

	it("shows auto-approve as off until its notice has been seen, since nothing runs unasked before", async () => {
		const approvalMode = useApprovalModeStore();
		// What the server sends at start-up for a user who never chose.
		approvalMode.apply({ available: true, on: true, notice_seen: false });
		const wrapper = mount(InputArea, {
			props: { isStreaming: false, interactionMode: null, context: null },
		});
		const toggle = () => wrapper.find("[data-auto-approve-toggle]");

		expect(wrapper.find(".aa-notice").exists()).toBe(true);
		expect(toggle().attributes("aria-pressed")).toBe("false");

		approvalMode.apply({ available: true, on: true, notice_seen: true });
		await nextTick();

		expect(wrapper.find(".aa-notice").exists()).toBe(false);
		expect(toggle().attributes("aria-pressed")).toBe("true");
	});
});
