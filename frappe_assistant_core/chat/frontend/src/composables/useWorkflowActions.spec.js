import { describe, it, expect, vi } from "vitest";
import { ref } from "vue";

vi.mock("@/api/client", () => ({
	api: { workflows: { triggers: { list: vi.fn().mockResolvedValue({ triggers: [] }) } } },
}));

import { useWorkflowActions } from "./useWorkflowActions";

function setup(status, warnings) {
	const workflowStore = { saveWorkflow: vi.fn().mockResolvedValue({}) };
	const preflight = { check: vi.fn().mockResolvedValue(warnings) };
	const actions = useWorkflowActions({
		workflowStore,
		workflowId: ref("WF-1"),
		currentWorkflow: ref({ status, workflow_name: "Digest" }),
		canEdit: ref(true),
		isDirty: ref(false),
		toGraphJson: () => "{}",
		hasSaved: ref(false),
		saveError: ref(null),
		preflight,
	});
	return { actions, workflowStore, preflight };
}

describe("activation gate", () => {
	it("holds a Draft with an unapproved write tool until the user confirms", async () => {
		const { actions, workflowStore } = setup("Draft", [{ tool: "create_document", server: "", nodes: ["Draft reply"] }]);
		await actions.requestToggleStatus();
		expect(workflowStore.saveWorkflow).not.toHaveBeenCalled();
		expect(actions.pendingActivation.value).toBe(true);
		await actions.confirmActivation();
		expect(workflowStore.saveWorkflow).toHaveBeenCalledWith("WF-1", { status: "Active" });
		expect(actions.pendingActivation.value).toBe(false);
	});

	it("activates straight away when every write is approved", async () => {
		const { actions, workflowStore } = setup("Paused", []);
		await actions.requestToggleStatus();
		expect(workflowStore.saveWorkflow).toHaveBeenCalledWith("WF-1", { status: "Active" });
		expect(actions.pendingActivation.value).toBe(false);
	});

	it("pauses without running the preflight", async () => {
		const { actions, workflowStore, preflight } = setup("Active", [{ tool: "x" }]);
		await actions.requestToggleStatus();
		expect(workflowStore.saveWorkflow).toHaveBeenCalledWith("WF-1", { status: "Paused" });
		expect(preflight.check).not.toHaveBeenCalled();
	});

	it("cancel leaves the status alone", async () => {
		const { actions, workflowStore } = setup("Draft", [{ tool: "x", nodes: [] }]);
		await actions.requestToggleStatus();
		actions.cancelActivation();
		expect(actions.pendingActivation.value).toBe(false);
		expect(workflowStore.saveWorkflow).not.toHaveBeenCalled();
	});
});
