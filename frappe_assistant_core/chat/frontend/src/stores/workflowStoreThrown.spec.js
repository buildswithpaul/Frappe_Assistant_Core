import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";

const api = vi.hoisted(() => ({
	workflows: { list: vi.fn(), listRuns: vi.fn(), listTemplates: vi.fn(), validateGraph: vi.fn() },
}));
vi.mock("@/api/client", () => ({ api }));

import { useWorkflowStore } from "@/stores/workflowStore";

describe("workflowStore thrown load errors", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		Object.values(api.workflows).forEach((f) => f.mockReset());
	});

	// production: a transport failure (timeout, 502) rejects the api call after an earlier success
	it("loadWorkflows clears the list when a later load throws", async () => {
		const store = useWorkflowStore();
		api.workflows.list.mockResolvedValueOnce({
			workflows: [{ name: "A" }],
			total: 1,
			page: 0,
		});
		await store.loadWorkflows();
		api.workflows.list.mockRejectedValueOnce(new Error("boom"));
		await store.loadWorkflows();
		expect(store.workflows).toEqual([]);
		expect(store.listError).toBe("boom");
	});

	it("loadRuns clears the runs when a later load throws, but keeps them on a failed append", async () => {
		const store = useWorkflowStore();
		api.workflows.listRuns.mockResolvedValueOnce({ runs: [{ name: "R1" }], total: 2 });
		await store.loadRuns("WF", null, 0);
		api.workflows.listRuns.mockRejectedValueOnce(new Error("page down"));
		await store.loadRuns("WF", null, 1, { append: true });
		expect(store.runs).toHaveLength(1);
		api.workflows.listRuns.mockRejectedValueOnce(new Error("boom"));
		await store.loadRuns("WF", null, 0);
		expect(store.runs).toEqual([]);
		expect(store.runsError).toBe("boom");
	});

	it("loadTemplates keeps rows and total on a failed append", async () => {
		const store = useWorkflowStore();
		api.workflows.listTemplates.mockResolvedValueOnce({
			templates: [{ name: "T1" }],
			total: 2,
		});
		await store.loadTemplates();
		api.workflows.listTemplates.mockResolvedValueOnce({
			templates: [],
			total: 0,
			error: "down",
		});
		await store.loadTemplates(null, null, null, 1, { append: true });
		expect(store.templates).toHaveLength(1);
		expect(store.templatesTotal).toBe(2);
		expect(store.templatesError).toBe("down");
	});

	// production: a timeout or 502 rejects the call; a real rejection arrives as {valid:false}
	it("validateGraph marks a rejected call as a transport failure, not a verdict", async () => {
		const store = useWorkflowStore();
		api.workflows.validateGraph.mockRejectedValueOnce(new Error("Failed to fetch"));
		expect(await store.validateGraph("{}")).toEqual({
			valid: false,
			transport: true,
			error: "Failed to fetch",
		});
	});
});
