import { describe, it, expect, vi } from "vitest";
import { nextTick, watch } from "vue";
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

	it("opening a trigger's run focuses it, shows Runs and hides Audit", async () => {
		const p = useBuilderPanels();
		p.onToggleAudit();
		await p.onOpenRun("WFR-00012");
		expect([p.focusRunName.value, p.showRunsPanel.value, p.showAuditPanel.value]).toEqual([
			"WFR-00012",
			true,
			false,
		]);
	});

	it("closing Run history forgets the focused run, however it closes", async () => {
		const p = useBuilderPanels();
		await p.onOpenRun("WFR-00012");
		p.onToggleRuns();
		await nextTick();
		expect(p.focusRunName.value).toBe("");
		await p.onOpenRun("WFR-00013");
		p.showRunsPanel.value = false;
		await nextTick();
		expect(p.focusRunName.value).toBe("");
	});

	it("opening the same run again after it was collapsed focuses it again", async () => {
		const p = useBuilderPanels();
		const seen = [];
		watch(p.focusRunName, (v) => seen.push(v));
		await p.onOpenRun("WFR-00012");
		await nextTick();
		p.onToggleRuns();
		await nextTick();
		await p.onOpenRun("WFR-00012");
		await nextTick();
		expect(p.focusRunName.value).toBe("WFR-00012");
		expect(seen).toEqual(["WFR-00012", "", "WFR-00012"]);
	});

	it("opening the same run while Run history is open still re-focuses it", async () => {
		const p = useBuilderPanels();
		const seen = [];
		watch(p.focusRunName, (v) => seen.push(v));
		await p.onOpenRun("WFR-00012");
		await nextTick();
		await p.onOpenRun("WFR-00012");
		await nextTick();
		expect(seen).toEqual(["WFR-00012", "", "WFR-00012"]);
	});
});
