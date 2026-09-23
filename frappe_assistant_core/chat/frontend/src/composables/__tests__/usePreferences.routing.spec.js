import { describe, it, expect, beforeEach } from "vitest";
import { usePreferences } from "../usePreferences.js";

describe("showRoutingChip", () => {
	beforeEach(() => localStorage.clear());

	it("defaults on — the annotation is the point of the feature", () => {
		const { preferences } = usePreferences();
		expect(preferences.showRoutingChip).toBe(true);
	});

	it("survives a save/load round trip when switched off", () => {
		const { preferences, savePreferences } = usePreferences();
		preferences.showRoutingChip = false;
		savePreferences();
		const stored = JSON.parse(localStorage.getItem("faco-preferences"));
		expect(stored.showRoutingChip).toBe(false);
		preferences.showRoutingChip = true;
		savePreferences();
	});

	it("is offered in the settings UI", async () => {
		const src = await import(
			"../../components/settings/AppearanceSettings.vue?raw"
		);
		expect(src.default).toContain("showRoutingChip");
	});
});
