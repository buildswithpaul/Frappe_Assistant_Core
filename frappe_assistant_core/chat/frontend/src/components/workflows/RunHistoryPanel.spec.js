import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

const listRuns = vi.fn();
vi.mock("@/api/client", () => ({
	api: { workflows: { listRuns: (...a) => listRuns(...a), getRun: vi.fn() } },
}));

import RunHistoryPanel from "@/components/workflows/RunHistoryPanel.vue";

describe("RunHistoryPanel", () => {
	beforeEach(() => {
		listRuns.mockReset();
		setActivePinia(createPinia());
	});

	it("shows an outage with Retry instead of 'No runs yet'", async () => {
		listRuns.mockResolvedValue({ runs: [], total: 0, error: "runs down" });
		const w = mount(RunHistoryPanel, { props: { workflowId: "WF-1" } });
		await flushPromises();
		expect(w.text()).toContain("runs down");
		expect(w.text()).not.toContain("No runs yet");
		listRuns.mockResolvedValue({ runs: [{ name: "R1", status: "Completed" }], total: 1 });
		await w.get('[role="alert"] button').trigger("click");
		await flushPromises();
		expect(listRuns).toHaveBeenCalledTimes(2);
	});

	// regression guard: the Load more append fix landed in an earlier task
	it("Load more shows page 1 and page 2 together", async () => {
		listRuns
			.mockResolvedValueOnce({ runs: [{ name: "R1", status: "Completed" }], total: 2 })
			.mockResolvedValueOnce({ runs: [{ name: "R2", status: "Failed" }], total: 2 });
		const w = mount(RunHistoryPanel, { props: { workflowId: "WF-1" } });
		await flushPromises();
		await w.get(".load-more-btn").trigger("click");
		await flushPromises();
		expect(w.findAll(".run-card")).toHaveLength(2);
	});

	it("a failed Load more leaves the page counter so a retry asks for the same page", async () => {
		listRuns
			.mockResolvedValueOnce({ runs: [{ name: "R1", status: "Completed" }], total: 3 })
			.mockResolvedValueOnce({ runs: [], total: 0, error: "page down" })
			.mockResolvedValueOnce({ runs: [{ name: "R2", status: "Failed" }], total: 3 });
		const w = mount(RunHistoryPanel, { props: { workflowId: "WF-1" } });
		await flushPromises();
		await w.get(".load-more-btn").trigger("click");
		await flushPromises();
		await w.get(".load-more-btn").trigger("click");
		await flushPromises();
		expect(listRuns.mock.calls[1][2]).toBe(1);
		expect(listRuns.mock.calls[2][2]).toBe(1);
	});
});
