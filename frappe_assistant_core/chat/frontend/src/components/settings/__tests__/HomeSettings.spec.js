import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getPreferences, updatePreferences, showError } = vi.hoisted(() => ({
	getPreferences: vi.fn(),
	updatePreferences: vi.fn(),
	showError: vi.fn(),
}));
vi.mock("@/api/client", () => ({
	api: { home: { getPreferences: (...a) => getPreferences(...a), updatePreferences: (...a) => updatePreferences(...a) } },
}));
vi.mock("@/composables/useToast", () => ({ useToast: () => ({ showError }) }));

import HomeSettings from "../HomeSettings.vue";

const PREFS = {
	show_needs_you: true,
	needs_you_count: 3,
	hidden_signals: ["todos"],
	show_suggested_prompts: true,
	show_personalized_suggestions: true,
	signals: [
		{ id: "approvals", label: "Approvals waiting for you" },
		{ id: "todos", label: "ToDos due" },
		{ id: "failed_workflows", label: "Failed workflows" },
	],
};

async function mountSettings(prefs = PREFS) {
	getPreferences.mockResolvedValue(prefs);
	const w = mount(HomeSettings);
	await flushPromises();
	return w;
}

describe("HomeSettings", () => {
	beforeEach(() => {
		getPreferences.mockReset();
		updatePreferences.mockReset().mockImplementation(async (patch) => ({ ...PREFS, ...patch }));
		showError.mockReset();
	});

	it("explains the AI cost of personalised suggestions", async () => {
		const w = await mountSettings();
		expect(w.text()).toContain("Uses AI about once a day to suggest questions for you. Turn off to save usage.");
	});

	it("each toggle saves just its own field", async () => {
		const w = await mountSettings();
		await w.find("#home-show_needs_you").setValue(false);
		expect(updatePreferences).toHaveBeenLastCalledWith({ show_needs_you: false });
		await w.find("#home-show_suggested_prompts").setValue(false);
		expect(updatePreferences).toHaveBeenLastCalledWith({ show_suggested_prompts: false });
		await w.find("#home-show_personalized_suggestions").setValue(false);
		expect(updatePreferences).toHaveBeenLastCalledWith({ show_personalized_suggestions: false });
	});

	it("the cards select saves a number", async () => {
		const w = await mountSettings();
		await w.find("#home-needs-you-count").setValue("2");
		expect(updatePreferences).toHaveBeenCalledWith({ needs_you_count: 2 });
	});

	it("the checklist shows ticked unless hidden, and saves the new hidden list", async () => {
		const w = await mountSettings();
		expect(w.find("#signal-approvals").element.checked).toBe(true);
		expect(w.find("#signal-todos").element.checked).toBe(false);
		await w.find("#signal-approvals").setValue(false);
		expect(updatePreferences).toHaveBeenLastCalledWith({ hidden_signals: ["todos", "approvals"] });
		await w.find("#signal-todos").setValue(true);
		expect(updatePreferences).toHaveBeenLastCalledWith({ hidden_signals: ["approvals"] });
	});

	it("includes failed workflows in the checklist", async () => {
		const w = await mountSettings();
		expect(w.find("#signal-failed_workflows").exists()).toBe(true);
	});

	it("disables the checklist and the count when Needs you is off", async () => {
		const w = await mountSettings({ ...PREFS, show_needs_you: false });
		expect(w.find("fieldset.signals").attributes("disabled")).toBeDefined();
		expect(w.find("#home-needs-you-count").attributes("disabled")).toBeDefined();
	});

	it("restores the control and reports when a save fails", async () => {
		updatePreferences.mockRejectedValue(new Error("nope"));
		const w = await mountSettings();
		await w.find("#home-show_suggested_prompts").setValue(false);
		await flushPromises();
		expect(showError).toHaveBeenCalledWith("nope");
		expect(w.find("#home-show_suggested_prompts").element.checked).toBe(true);
	});
});
