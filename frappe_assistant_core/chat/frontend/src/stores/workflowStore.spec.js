import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";

const workflowsApi = {
	execute: vi.fn(),
	getRun: vi.fn(),
	cancelRun: vi.fn(),
	listRuns: vi.fn(),
	get: vi.fn(),
	create: vi.fn(),
	update: vi.fn(),
	list: vi.fn(),
	listTemplates: vi.fn(),
};
const modelsApi = { getAvailable: vi.fn() };
const userApi = { listTools: vi.fn() };

vi.mock("@/api/client", () => ({
	api: {
		get workflows() {
			return workflowsApi;
		},
		get models() {
			return modelsApi;
		},
		get user() {
			return userApi;
		},
	},
}));

import { useWorkflowStore } from "@/stores/workflowStore";

describe("workflowStore run polling", () => {
	let store;

	beforeEach(() => {
		vi.useFakeTimers();
		setActivePinia(createPinia());
		store = useWorkflowStore();
		for (const fn of Object.values(workflowsApi)) fn.mockReset();
		workflowsApi.listRuns.mockResolvedValue({ runs: [], total: 0 });
		workflowsApi.list.mockResolvedValue({ workflows: [], total: 0, page: 0 });
	});

	afterEach(() => {
		store.stopRunPolling();
		vi.useRealTimers();
	});

	it("starts polling when a run is launched", async () => {
		workflowsApi.execute.mockResolvedValue({ run_name: "RUN-1" });
		workflowsApi.getRun.mockResolvedValue({ name: "RUN-1", status: "Running" });

		await store.executeWorkflow("WF-1");
		expect(store.isRunning).toBe(true);

		await vi.advanceTimersByTimeAsync(2000);
		expect(workflowsApi.getRun).toHaveBeenCalledWith("RUN-1");
		expect(store.isRunning).toBe(true);
	});

	it("stops on every terminal status, Cancelled and Timed Out included", async () => {
		for (const status of ["Completed", "Failed", "Cancelled", "Timed Out"]) {
			workflowsApi.execute.mockResolvedValue({ run_name: "RUN-1" });
			workflowsApi.getRun.mockResolvedValue({ name: "RUN-1", status });

			await store.executeWorkflow("WF-1");
			await vi.advanceTimersByTimeAsync(2000);

			expect(store.isRunning, status).toBe(false);
			expect(store.activeRunName, status).toBeNull();
		}
	});

	it("keeps polling the live run when a historic run is opened", async () => {
		workflowsApi.execute.mockResolvedValue({ run_name: "RUN-2" });
		workflowsApi.getRun.mockResolvedValue({ name: "RUN-2", status: "Running" });
		await store.executeWorkflow("WF-1");

		workflowsApi.getRun.mockResolvedValue({ name: "RUN-1", status: "Completed" });
		await store.loadRun("RUN-1");

		expect(store.isRunning).toBe(true);
		expect(store.activeRunName).toBe("RUN-2");
	});

	it("does not refund or clear the run on cancel — it waits for the engine", async () => {
		workflowsApi.execute.mockResolvedValue({ run_name: "RUN-1" });
		workflowsApi.getRun.mockResolvedValue({ name: "RUN-1", status: "Running" });
		await store.executeWorkflow("WF-1");

		workflowsApi.cancelRun.mockResolvedValue({ status: "cancelling" });
		await store.cancelRun("RUN-1");

		expect(store.isCancelling).toBe(true);
		expect(store.isRunning).toBe(true);

		workflowsApi.getRun.mockResolvedValue({ name: "RUN-1", status: "Cancelled" });
		await vi.advanceTimersByTimeAsync(2000);
		expect(store.isRunning).toBe(false);
		expect(store.isCancelling).toBe(false);
	});

	it("stops the timer when the builder is left", async () => {
		workflowsApi.execute.mockResolvedValue({ run_name: "RUN-1" });
		workflowsApi.getRun.mockResolvedValue({ name: "RUN-1", status: "Running" });
		await store.executeWorkflow("WF-1");

		store.clearCurrentWorkflow();
		workflowsApi.getRun.mockClear();
		await vi.advanceTimersByTimeAsync(6000);
		expect(workflowsApi.getRun).not.toHaveBeenCalled();
	});
});

describe("workflowStore.loadModels", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		modelsApi.getAvailable.mockReset();
	});

	it("keeps the model list an array when the terms gate answers with an error", async () => {
		const store = useWorkflowStore();
		modelsApi.getAvailable.mockResolvedValue({
			error: "Terms update required",
			error_code: "TERMS_UPDATE_REQUIRED",
		});
		await store.loadModels();
		expect(store.availableModels).toEqual([]);
		expect(store.modelsError).toBe("Terms update required");
	});

	it("loads models on the happy path", async () => {
		const store = useWorkflowStore();
		modelsApi.getAvailable.mockResolvedValue({
			success: true,
			models: [{ model_id: "m", display_name: "M", tier: "Standard", tier_rank: 1 }],
		});
		await store.loadModels();
		expect(store.availableModels).toHaveLength(1);
		expect(store.modelsError).toBeNull();
	});
});

describe("workflowStore.loadRuns paging", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		store = useWorkflowStore();
		for (const fn of Object.values(workflowsApi)) fn.mockReset();
	});

	it("appends the next page instead of replacing the first", async () => {
		workflowsApi.listRuns
			.mockResolvedValueOnce({ runs: [{ name: "R1" }, { name: "R2" }], total: 3 })
			.mockResolvedValueOnce({ runs: [{ name: "R3" }], total: 3 });

		await store.loadRuns("WF-1", null, 0);
		await store.loadRuns("WF-1", null, 1, { append: true });

		expect(store.runs.map((r) => r.name)).toEqual(["R1", "R2", "R3"]);
		expect(workflowsApi.listRuns).toHaveBeenLastCalledWith("WF-1", null, 1, 20);
	});

	it("does not duplicate a run that moved onto the next page", async () => {
		workflowsApi.listRuns
			.mockResolvedValueOnce({ runs: [{ name: "R1" }, { name: "R2" }], total: 4 })
			.mockResolvedValueOnce({ runs: [{ name: "R2" }, { name: "R3" }], total: 4 });

		await store.loadRuns("WF-1", null, 0);
		await store.loadRuns("WF-1", null, 1, { append: true });

		expect(store.runs.map((r) => r.name)).toEqual(["R1", "R2", "R3"]);
	});
});

describe("workflowStore outage vs empty", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		store = useWorkflowStore();
		for (const fn of Object.values(workflowsApi)) fn.mockReset();
	});

	it("keeps an empty list error-free", async () => {
		workflowsApi.list.mockResolvedValue({ workflows: [], total: 0, page: 0 });
		await store.loadWorkflows();
		expect(store.listError).toBe(null);
	});

	it("surfaces the endpoint's outage message", async () => {
		workflowsApi.list.mockResolvedValue({ workflows: [], total: 0, error: "FAC Cloud down" });
		await store.loadWorkflows();
		expect(store.listError).toBe("FAC Cloud down");
	});

	it("surfaces a thrown call as an outage", async () => {
		workflowsApi.list.mockRejectedValue(new Error("Can't reach the server."));
		await store.loadWorkflows();
		expect(store.listError).toBe("Can't reach the server.");
	});

	it("tracks run and template outages separately", async () => {
		workflowsApi.listRuns.mockResolvedValue({ runs: [], total: 0, error: "runs down" });
		workflowsApi.listTemplates.mockResolvedValue({ templates: [], total: 0, error: "tpl down" });
		await store.loadRuns("WF-1");
		await store.loadTemplates();
		expect(store.runsError).toBe("runs down");
		expect(store.templatesError).toBe("tpl down");
		expect(store.listError).toBe(null);
	});
});

describe("workflowStore tool inventory", () => {
	let store;
	const result = (name) => ({ success: true, tools: [{ name, server: "Main Frappe Site" }] });

	beforeEach(() => {
		setActivePinia(createPinia());
		store = useWorkflowStore();
		userApi.listTools.mockReset();
	});

	it("asks for the named runtime user's tools", async () => {
		userApi.listTools.mockResolvedValue(result("a"));
		await store.loadTools("ops@example.com");
		expect(userApi.listTools).toHaveBeenCalledWith("ops@example.com");
	});

	it("does not refetch for the same runtime user, but does for another", async () => {
		userApi.listTools.mockResolvedValueOnce(result("a")).mockResolvedValueOnce(result("b"));
		await store.loadTools("ops@example.com");
		await store.loadTools("ops@example.com");
		expect(userApi.listTools).toHaveBeenCalledTimes(1);
		await store.loadTools("sales@example.com");
		expect(userApi.listTools).toHaveBeenCalledTimes(2);
		expect(store.availableTools[0].name).toBe("b");
	});

	it("forgets the inventory when the builder closes", async () => {
		userApi.listTools.mockResolvedValue(result("a"));
		await store.loadTools("ops@example.com");
		store.clearCurrentWorkflow();
		expect(store.toolsResult).toBeNull();
		expect(store.availableTools).toEqual([]);
		await store.loadTools("ops@example.com");
		expect(userApi.listTools).toHaveBeenCalledTimes(2);
	});

	it("refetches when forced, e.g. after reconnecting a server", async () => {
		userApi.listTools.mockResolvedValue(result("a"));
		await store.loadTools(null);
		await store.loadTools(null, { force: true });
		expect(userApi.listTools).toHaveBeenCalledTimes(2);
	});

	it("lets the latest runtime user win when responses arrive out of order", async () => {
		let releaseFirst;
		userApi.listTools
			.mockReturnValueOnce(new Promise((resolve) => (releaseFirst = resolve)))
			.mockResolvedValueOnce(result("second"));
		const first = store.loadTools("ops@example.com");
		await store.loadTools("sales@example.com");
		releaseFirst(result("first"));
		await first;
		expect(store.availableTools[0].name).toBe("second");
	});
});
