import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";

import InputToolbar from "@/components/chat/InputToolbar.vue";
import AutoApproveNotice from "@/components/chat/AutoApproveNotice.vue";

const toolbar = (props = {}) =>
	mount(InputToolbar, { props, global: { stubs: { MicButton: true } } });
const toggle = (wrapper) => wrapper.find("[data-auto-approve-toggle]");

describe("the composer's auto-approve switch", () => {
	it("is not shown on a site whose FAC Cloud does not offer the mode", () => {
		expect(toggle(toolbar()).exists()).toBe(false);
	});

	it("shows whether the mode is on and asks to flip it", async () => {
		const wrapper = toolbar({ autoApproveAvailable: true, autoApprove: true });

		expect(toggle(wrapper).attributes("aria-pressed")).toBe("true");
		expect(toggle(wrapper).classes()).toContain("toolbar-btn-active");
		await toggle(wrapper).trigger("click");
		expect(wrapper.emitted("toggle-auto-approve")).toHaveLength(1);

		const off = toolbar({ autoApproveAvailable: true, autoApprove: false });
		expect(toggle(off).attributes("aria-pressed")).toBe("false");
		expect(toggle(off).attributes("title")).toContain("every change asks first");
	});

	it("stays usable while the assistant is answering, and waits while a flip is saving", () => {
		const streaming = toolbar({ autoApproveAvailable: true, autoApprove: true, isStreaming: true });
		expect(toggle(streaming).attributes("disabled")).toBeUndefined();

		const saving = toolbar({ autoApproveAvailable: true, autoApprove: true, autoApproveSaving: true });
		expect(toggle(saving).attributes("disabled")).toBeDefined();
	});
});

describe("the one-time auto-approve notice", () => {
	it("says what still asks and offers to keep the mode or turn it off", async () => {
		const wrapper = mount(AutoApproveNotice);

		expect(wrapper.text()).toContain("Once you choose Got it");
		expect(wrapper.text()).toContain("Submitting, deleting, emailing, publishing and admin changes still ask");
		expect(wrapper.text()).toContain("An edit has no Undo");
		const [turnOff, keep] = wrapper.findAll("button");
		await turnOff.trigger("click");
		await keep.trigger("click");
		expect(wrapper.emitted("turn-off")).toHaveLength(1);
		expect(wrapper.emitted("keep")).toHaveLength(1);
	});
});
