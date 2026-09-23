import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import ComposerPlusMenu from "../ComposerPlusMenu.vue";

describe("ComposerPlusMenu", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
	});

	it("offers attach and thinking, and hides web search when unavailable", () => {
		const wrapper = mount(ComposerPlusMenu, {
			props: { open: true, webSearchAvailable: false, webSearch: false, thinking: false },
		});
		expect(wrapper.find(".menu-attach").exists()).toBe(true);
		expect(wrapper.find(".menu-thinking").exists()).toBe(true);
		expect(wrapper.find(".menu-web-search").exists()).toBe(false);
	});

	it("emits attach synchronously so the file dialog keeps its user gesture", async () => {
		const wrapper = mount(ComposerPlusMenu, {
			props: { open: true, webSearchAvailable: true, webSearch: false, thinking: false },
		});
		await wrapper.find(".menu-attach").trigger("click");
		expect(wrapper.emitted("attach")).toBeTruthy();
	});

	it("reflects an enabled mode with aria-pressed", () => {
		const wrapper = mount(ComposerPlusMenu, {
			props: { open: true, webSearchAvailable: true, webSearch: true, thinking: false },
		});
		expect(wrapper.find(".menu-web-search").attributes("aria-pressed")).toBe("true");
	});
});
