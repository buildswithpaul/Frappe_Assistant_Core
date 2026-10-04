import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { nextTick } from "vue";
import ModelSelector from "../ModelSelector.vue";
import { useModelStore } from "@/stores/modelStore";

describe("ModelSelector", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
	});

	it("opens when the store requests the picker and clears it on close", async () => {
		const modelStore = useModelStore();
		const wrapper = mount(ModelSelector);
		expect(wrapper.find(".model-dropdown").exists()).toBe(false);

		modelStore.openPicker();
		await nextTick();
		expect(wrapper.find(".model-dropdown").exists()).toBe(true);

		document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
		await nextTick();
		expect(modelStore.pickerOpen).toBe(false);
		expect(wrapper.find(".model-dropdown").exists()).toBe(false);
		wrapper.unmount();
	});
});
