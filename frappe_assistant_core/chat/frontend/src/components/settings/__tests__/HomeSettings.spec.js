import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getPreferences, updatePreferences, showError, loadSuggestions } = vi.hoisted(() => ({
	loadSuggestions: vi.fn(),
	getPreferences: vi.fn(),
	updatePreferences: vi.fn(),
	showError: vi.fn(),
}));
vi.mock("@/api/client", () => ({
	api: { home: { getPreferences: (...a) => getPreferences(...a), updatePreferences: (...a) => updatePreferences(...a) } },
}));
vi.mock("@/stores/suggestionStore", () => ({ useSuggestionStore: () => ({ loadSuggestions }) }));
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
		loadSuggestions.mockReset();
	});

	it("explains the AI cost of personalised suggestions", async () => {
		const w = await mountSettings();
		expect(w.text()).toContain("Uses AI about once a day to suggest questions for you. Turn off to save usage.");
	});

	it("each toggle saves just its own field", async () => {
		const w = await mountSettings();
		await w.find("#home-show_needs_you").setValue(false);
		expect(updatePreferences).toHaveBeenLastCalledWith({ show_needs_you: false });
		await w.find("#home-show_personalized_suggestions").setValue(false);
		expect(updatePreferences).toHaveBeenLastCalledWith({ show_personalized_suggestions: false });
		await w.find("#home-show_suggested_prompts").setValue(false);
		expect(updatePreferences).toHaveBeenLastCalledWith({ show_suggested_prompts: false });
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

	it("changing a suggestions toggle forces the store to refetch; other changes do not", async () => {
		const w = await mountSettings();
		await w.find("#home-show_personalized_suggestions").setValue(false);
		await flushPromises();
		expect(loadSuggestions).toHaveBeenCalledWith({}, { force: true });
		loadSuggestions.mockReset();
		await w.find("#home-needs-you-count").setValue("2");
		await flushPromises();
		expect(loadSuggestions).not.toHaveBeenCalled();
	});

	it("does not refetch when the save fails", async () => {
		updatePreferences.mockRejectedValue(new Error("nope"));
		const w = await mountSettings();
		await w.find("#home-show_suggested_prompts").setValue(false);
		await flushPromises();
		expect(loadSuggestions).not.toHaveBeenCalled();
	});

	it("disables Personalised suggestions, with a hint, while Suggested questions is off", async () => {
		const w = await mountSettings({ ...PREFS, show_suggested_prompts: false });
		const toggle = w.find("#home-show_personalized_suggestions");
		expect(toggle.attributes("disabled")).toBeDefined();
		expect(toggle.attributes("aria-disabled")).toBe("true");
		expect(toggle.attributes("aria-describedby")).toBe("home-show_personalized_suggestions-hint");
		expect(w.find("#home-show_personalized_suggestions-hint").text()).toBe(
			"Turn on Suggested questions to use this."
		);
		await w.find("#home-show_suggested_prompts").setValue(true);
		await flushPromises();
		expect(w.find("#home-show_personalized_suggestions").attributes("disabled")).toBeUndefined();
		expect(w.find("#home-show_personalized_suggestions-hint").exists()).toBe(false);
	});

	it("the latest save wins when an older response arrives last", async () => {
		let finishFirst;
		updatePreferences.mockReset();
		updatePreferences
			.mockImplementationOnce(() => new Promise((resolve) => (finishFirst = resolve)))
			.mockImplementationOnce(async (patch) => ({ ...PREFS, ...patch }));
		const w = await mountSettings();
		await w.find("#home-show_suggested_prompts").setValue(false);
		await w.find("#home-needs-you-count").setValue("2");
		await flushPromises();
		finishFirst({ ...PREFS, show_suggested_prompts: false });
		await flushPromises();
		// The older response carries the old count of 3; it must not overwrite the newer choice of 2.
		expect(w.find("#home-needs-you-count").element.value).toBe("2");
	});

	it("says so, and shows no controls, when the settings cannot be loaded", async () => {
		getPreferences.mockRejectedValue(new Error("down"));
		const w = mount(HomeSettings);
		await flushPromises();
		expect(w.find("[role=alert]").text()).toBe(
			"Your home page settings could not be loaded. Refresh the page to try again."
		);
		expect(w.find("input").exists()).toBe(false);
	});
});
