import { mount } from "@vue/test-utils";
import { describe, it, expect, beforeEach } from "vitest";
import AppearanceSettings from "../AppearanceSettings.vue";
import { usePreferences } from "@/composables/usePreferences";

function mountSettings() {
	return mount(AppearanceSettings);
}

function toggleFor(wrapper, label) {
	const row = wrapper
		.findAll(".setting-item")
		.find((item) => item.find(".setting-label").text() === label);
	return row.find("input[type='checkbox']");
}

describe("AppearanceSettings — Wide chat layout toggle", () => {
	beforeEach(() => {
		localStorage.clear();
		const { preferences } = usePreferences();
		preferences.chatWidth = "wide";
	});

	it("renders the toggle in the Display section, checked when wide", () => {
		expect(toggleFor(mountSettings(), "Wide chat layout").element.checked).toBe(true);
	});

	it("switches to cozy and persists on toggle off", async () => {
		const wrapper = mountSettings();
		await toggleFor(wrapper, "Wide chat layout").setValue(false);
		const { preferences } = usePreferences();
		expect(preferences.chatWidth).toBe("cozy");
		expect(JSON.parse(localStorage.getItem("faco-preferences")).chatWidth).toBe("cozy");
	});

	it("switches back to wide on toggle on", async () => {
		const { preferences } = usePreferences();
		preferences.chatWidth = "cozy";
		const wrapper = mountSettings();
		expect(toggleFor(wrapper, "Wide chat layout").element.checked).toBe(false);
		await toggleFor(wrapper, "Wide chat layout").setValue(true);
		expect(preferences.chatWidth).toBe("wide");
	});
});

describe("AppearanceSettings — page contract", () => {
	beforeEach(() => localStorage.clear());

	it("carries every display preference moved off Profile", () => {
		const labels = mountSettings()
			.findAll(".setting-label")
			.map((l) => l.text());
		expect(labels).toEqual([
			"Wide chat layout",
			"Show message timestamps",
			"Explain how replies ran",
			"Reduce motion",
			"High contrast mode",
			"Large text",
		]);
	});

	it("has no save button — every toggle commits on change", () => {
		const wrapper = mountSettings();
		expect(wrapper.find(".save-bar").exists()).toBe(false);
		expect(wrapper.findAll("button").length).toBe(0);
	});

	it("says the preferences are local to this browser", () => {
		expect(mountSettings().text()).toContain("this browser");
	});
});
