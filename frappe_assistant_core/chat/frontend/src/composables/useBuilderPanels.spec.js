import { describe, it, expect, vi } from "vitest";
import { useBuilderPanels } from "./useBuilderPanels";

describe("useBuilderPanels", () => {
	it("Runs and Audit share the rail", () => {
		const p = useBuilderPanels();
		p.onToggleRuns();
		p.onToggleAudit();
		expect([p.showRunsPanel.value, p.showAuditPanel.value]).toEqual([false, true]);
	});

	it("routes each checklist action to its panel and closes the checklist", () => {
		const p = useBuilderPanels();
		p.showSetup.value = true;
		p.onSetupAction("schedule", {});
		p.onSetupAction("triggers", {});
		p.onSetupAction("settings", {});
		expect(p.showScheduleModal.value && p.showTriggersModal.value && p.showSettingsDrawer.value).toBe(true);
		expect(p.showSetup.value).toBe(false);
	});

	it("re-check refreshes in place and keeps the checklist open", () => {
		const p = useBuilderPanels();
		p.showSetup.value = true;
		const setup = { refresh: vi.fn() };
		p.onSetupAction("recheck", setup);
		expect(setup.refresh).toHaveBeenCalled();
		expect(p.showSetup.value).toBe(true);
	});

	it("Escape closes the checklist, then the settings drawer, then reports nothing to close", () => {
		const p = useBuilderPanels();
		p.showSetup.value = true;
		p.showSettingsDrawer.value = true;
		expect(p.closeOnEscape()).toBe(true);
		expect([p.showSetup.value, p.showSettingsDrawer.value]).toEqual([false, true]);
		expect(p.closeOnEscape()).toBe(true);
		expect(p.closeOnEscape()).toBe(false);
	});
});
