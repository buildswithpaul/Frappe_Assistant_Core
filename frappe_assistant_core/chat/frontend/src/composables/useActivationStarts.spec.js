import { describe, it, expect, vi, beforeEach } from "vitest";
import { ref } from "vue";

const { toggle } = vi.hoisted(() => ({ toggle: vi.fn().mockResolvedValue({}) }));
vi.mock("@/api/client", () => ({ api: { workflows: { triggers: { toggle } } } }));

import { useActivationStarts } from "./useActivationStarts";

function setup({ schedule = {}, triggers = [] } = {}) {
	const workflowStore = { setSchedule: vi.fn().mockResolvedValue({}) };
	const scheduleConfig = ref({ cron: "", timezone: "UTC", defaultInput: "", enabled: false, ...schedule });
	const triggersRef = ref(triggers);
	const { enableStarts } = useActivationStarts({
		workflowStore,
		workflowId: ref("WF-1"),
		scheduleConfig,
		triggers: triggersRef,
		browserZone: "Asia/Kolkata",
	});
	return { enableStarts, workflowStore, scheduleConfig, triggersRef };
}

describe("enableStarts", () => {
	beforeEach(() => toggle.mockClear());

	it("switches an imported schedule on, in the proposed zone", async () => {
		// Marketplace import saves the template's cron switched off and in UTC.
		const { enableStarts, workflowStore, scheduleConfig } = setup({ schedule: { cron: "0 9 * * 1" } });
		await enableStarts({ fromDraft: true });
		expect(workflowStore.setSchedule).toHaveBeenCalledWith("WF-1", "0 9 * * 1", "Asia/Kolkata", true, null);
		expect(scheduleConfig.value.enabled).toBe(true);
		expect(scheduleConfig.value.timezone).toBe("Asia/Kolkata");
	});

	it("leaves an already-enabled schedule alone", async () => {
		const { enableStarts, workflowStore } = setup({ schedule: { cron: "0 9 * * 1", enabled: true } });
		await enableStarts({ fromDraft: false });
		expect(workflowStore.setSchedule).not.toHaveBeenCalled();
	});

	it("turns on every switched-off trigger of a draft", async () => {
		// Marketplace import creates a template's suggested trigger with enabled=0.
		const { enableStarts, triggersRef } = setup({
			triggers: [{ name: "T1", enabled: 0 }, { name: "T2", enabled: 1 }],
		});
		await enableStarts({ fromDraft: true });
		expect(toggle).toHaveBeenCalledTimes(1);
		expect(toggle).toHaveBeenCalledWith("T1", true);
		expect(triggersRef.value[0].enabled).toBe(1);
	});

	it("does not touch triggers someone switched off on a paused agent", async () => {
		const { enableStarts } = setup({ triggers: [{ name: "T1", enabled: 0 }] });
		await enableStarts({ fromDraft: false });
		expect(toggle).not.toHaveBeenCalled();
	});

	it("turns triggers on before the schedule, whose save may flip a draft to Active", async () => {
		const order = [];
		toggle.mockImplementationOnce(async () => order.push("trigger"));
		const { enableStarts, workflowStore } = setup({
			schedule: { cron: "0 9 * * 1" },
			triggers: [{ name: "T1", enabled: 0 }],
		});
		workflowStore.setSchedule.mockImplementation(async () => order.push("schedule"));
		await enableStarts({ fromDraft: true });
		expect(order).toEqual(["trigger", "schedule"]);
	});

	it("passes a failure up so the status is not saved", async () => {
		toggle.mockRejectedValueOnce(new Error("refused"));
		const { enableStarts } = setup({ triggers: [{ name: "T1", enabled: 0 }] });
		await expect(enableStarts({ fromDraft: true })).rejects.toThrow("refused");
	});
});
