import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { nextTick } from "vue";
import ModelSelector from "../ModelSelector.vue";
import { useModelStore } from "@/stores/modelStore";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

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

	it("closes the picker when it unmounts, so it cannot reopen by itself", async () => {
		const modelStore = useModelStore();
		const wrapper = mount(ModelSelector);
		modelStore.openPicker();
		await nextTick();
		wrapper.unmount();
		expect(modelStore.pickerOpen).toBe(false);
	});

	// Redmine #34381: on a phone the trigger showed only an icon, so the chosen model was hidden.
	it("shows the chosen model's short name for phones", async () => {
		const modelStore = useModelStore();
		modelStore.models = [{ model_id: "sonnet", display_name: "Claude Sonnet 4.6" }];
		modelStore.defaultModel = "sonnet";
		const wrapper = mount(ModelSelector);
		await nextTick();
		expect(wrapper.find(".model-name-short").text()).toBe("Sonnet 4.6");
		expect(wrapper.find("button").attributes("title")).toBe("Claude Sonnet 4.6");
		wrapper.unmount();
	});

	it("shows Auto as itself", async () => {
		const modelStore = useModelStore();
		// AR enables auto mode in the models payload; the user then picks it from the menu.
		modelStore.autoMode = { enabled: true };
		modelStore.setSelectedModel("auto");
		const wrapper = mount(ModelSelector);
		await nextTick();
		expect(wrapper.find(".model-name-short").text()).toBe("Auto");
		wrapper.unmount();
	});
});

// jsdom injects no scoped CSS, so the phone rule is read from the source.
describe("ModelSelector on a phone", () => {
	const __dirname = dirname(fileURLToPath(import.meta.url));
	const css = readFileSync(join(__dirname, "../ModelTrigger.vue"), "utf8");

	it("swaps the icon and full name for the short name, never hiding the name", () => {
		const phone = css.match(/@media \(max-width: 640px\)\s*\{([\s\S]*?)\n\}/);
		expect(phone).not.toBeNull();
		expect(phone[1]).toMatch(/\.model-name-short\s*\{[^}]*display:\s*inline/);
		expect(phone[1]).toMatch(/\.model-icon,\s*\.model-name\s*\{[^}]*display:\s*none/);
	});
});

