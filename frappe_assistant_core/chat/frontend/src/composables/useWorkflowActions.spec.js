import { describe, it, expect, vi } from "vitest";
import { ref } from "vue";

const { list, update } = vi.hoisted(() => ({
	list: vi.fn().mockResolvedValue({ triggers: [] }),
	update: vi.fn().mockResolvedValue({}),
}));
vi.mock("@/api/client", () => ({ api: { workflows: { triggers: { list, update } } } }));

import { useWorkflowActions } from "./useWorkflowActions";

function setup(status, warnings, preflightOverrides = {}, notify = undefined) {
	const workflowStore = { saveWorkflow: vi.fn().mockResolvedValue({}) };
	const preflight = { check: vi.fn().mockResolvedValue(warnings), error: ref(null), ...preflightOverrides };
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
		notify,
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

	it("saves once when Activate is clicked twice during the check", async () => {
		let release;
		const { actions, workflowStore, preflight } = setup("Draft", []);
		preflight.check.mockImplementation(() => new Promise((r) => (release = () => r([]))));
		const first = actions.requestToggleStatus();
		const second = actions.requestToggleStatus();
		expect(actions.isCheckingActivation.value).toBe(true);
		release();
		await Promise.all([first, second]);
		expect(preflight.check).toHaveBeenCalledTimes(1);
		expect(workflowStore.saveWorkflow).toHaveBeenCalledTimes(1);
		expect(actions.isCheckingActivation.value).toBe(false);
	});

	it("says so when it activates without having been able to check", async () => {
		const notify = vi.fn();
		const { actions, workflowStore } = setup("Draft", [], { error: ref("down") }, notify);
		await actions.requestToggleStatus();
		expect(workflowStore.saveWorkflow).toHaveBeenCalledWith("WF-1", { status: "Active" });
		expect(notify).toHaveBeenCalledTimes(1);
	});

	it("stays quiet when the check ran", async () => {
		const notify = vi.fn();
		const { actions } = setup("Draft", [], {}, notify);
		await actions.requestToggleStatus();
		expect(notify).not.toHaveBeenCalled();
	});
});

describe("rename", () => {
	it("re-pins legacy triggers to the docname and never asks", async () => {
		window.confirm = vi.fn();
		list.mockResolvedValue({
			triggers: [
				{ name: "T-old", workflow_docname: "" },
				{ name: "T-new", workflow_docname: "WF-1" },
			],
		});
		const { actions, workflowStore } = setup("Draft", []);
		await actions.rename("Weekly Digest v2");
		expect(window.confirm).not.toHaveBeenCalled();
		expect(workflowStore.saveWorkflow).toHaveBeenCalledWith("WF-1", { workflow_name: "Weekly Digest v2" });
		expect(update).toHaveBeenCalledTimes(1);
		expect(update).toHaveBeenCalledWith("T-old", { workflow_docname: "WF-1" });
	});
});
