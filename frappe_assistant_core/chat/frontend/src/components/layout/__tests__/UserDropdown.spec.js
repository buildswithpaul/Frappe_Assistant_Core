import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import UserDropdown from "../UserDropdown.vue";

function openMenu() {
	const wrapper = mount(UserDropdown, {
		global: { plugins: [createPinia()] },
	});
	// The menu renders only once opened.
	wrapper.find(".user-dropdown-wrapper").trigger("click");
	return wrapper;
}

describe("UserDropdown — Docs link", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
	});

	it("points at the public site", async () => {
		const wrapper = openMenu();
		await wrapper.vm.$nextTick();

		const docs = wrapper
			.findAll("a.dropdown-menu-item")
			.find((a) => a.text().trim() === "Docs");

		expect(docs).toBeTruthy();
		expect(docs.attributes("href")).toBe("https://fac-suite.com/");
	});

	it("opens in a new tab without handing it a window opener", async () => {
		// `target=_blank` without `rel=noopener` lets the opened page reach back
		// through window.opener and redirect this tab — the reverse-tabnabbing
		// hole. The pair has to stay together, so assert both.
		const wrapper = openMenu();
		await wrapper.vm.$nextTick();

		const docs = wrapper
			.findAll("a.dropdown-menu-item")
			.find((a) => a.text().trim() === "Docs");

		expect(docs.attributes("target")).toBe("_blank");
		expect(docs.attributes("rel")).toContain("noopener");
	});

	it("is a real link, not a button that scripts a navigation", async () => {
		// An <a href> is what makes middle-click, cmd-click and "open in new
		// tab" work; a <button> + window.open silently breaks all three.
		const wrapper = openMenu();
		await wrapper.vm.$nextTick();

		const labels = wrapper.findAll("button.dropdown-menu-item").map((b) => b.text().trim());
		expect(labels).not.toContain("Docs");
	});

	it("closes the menu when followed", async () => {
		const wrapper = openMenu();
		await wrapper.vm.$nextTick();
		expect(wrapper.find(".user-dropdown-menu").exists()).toBe(true);

		const docs = wrapper
			.findAll("a.dropdown-menu-item")
			.find((a) => a.text().trim() === "Docs");
		await docs.trigger("click");

		expect(wrapper.find(".user-dropdown-menu").exists()).toBe(false);
	});
});
