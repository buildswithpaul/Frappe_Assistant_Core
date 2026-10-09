import { describe, it, expect, vi } from "vitest";
import { ref } from "vue";
import { useWorkflowExecution } from "./useWorkflowExecution";

function setup(save) {
	const workflowStore = { executeWorkflow: vi.fn().mockResolvedValue({ run_name: "R1" }) };
	const exec = useWorkflowExecution({
		workflowStore,
		workflowId: ref("WF-1"),
		canEdit: ref(true),
		isDirty: ref(true),
		nodes: ref([]),
		save,
		checkBeforeRun: () => true,
		scheduleConfig: ref({}),
		showRunsPanel: ref(false),
		showScheduleModal: ref(false),
	});
	return { exec, workflowStore };
}

describe("confirmRun", () => {
	it("does not start a run when the save before it failed", async () => {
		const { exec, workflowStore } = setup(vi.fn().mockResolvedValue(false));
		await exec.confirmRun("");
		expect(workflowStore.executeWorkflow).not.toHaveBeenCalled();
		expect(exec.actionError.value).toMatch(/not saved/);
	});

	it("runs after a successful save", async () => {
		const { exec, workflowStore } = setup(vi.fn().mockResolvedValue(true));
		await exec.confirmRun("");
		expect(workflowStore.executeWorkflow).toHaveBeenCalledWith("WF-1", null);
	});
});
