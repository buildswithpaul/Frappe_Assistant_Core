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
