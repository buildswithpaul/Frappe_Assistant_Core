import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

const listRuns = vi.fn();
const getRun = vi.fn();
const showError = vi.fn();
vi.mock("@/composables/useToast", () => ({
	useToast: () => ({ showError: (...a) => showError(...a) }),
}));
vi.mock("@/api/client", () => ({
	api: {
		workflows: { listRuns: (...a) => listRuns(...a), getRun: (...a) => getRun(...a) },
	},
}));

import RunHistoryPanel from "@/components/workflows/RunHistoryPanel.vue";
import RunCard from "@/components/workflows/RunCard.vue";

describe("RunHistoryPanel", () => {
	beforeEach(() => {
		listRuns.mockReset();
		getRun.mockReset();
		showError.mockReset();
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
		expect(w.find('[role="alert"]').exists()).toBe(false);
		expect(w.findAll(".run-card")).toHaveLength(1);
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

	it("shows the error inline next to Load more when a later page fails", async () => {
		listRuns
			.mockResolvedValueOnce({ runs: [{ name: "R1", status: "Completed" }], total: 3 })
			.mockResolvedValueOnce({ runs: [], total: 0, error: "page down" });
		const w = mount(RunHistoryPanel, { props: { workflowId: "WF-1" } });
		await flushPromises();
		await w.get(".load-more-btn").trigger("click");
		await flushPromises();
		expect(w.get(".inline-error").text()).toContain("page down");
		expect(w.findAll(".run-card")).toHaveLength(1);
	});

	it("expands a run it was asked to focus, even off the loaded page", async () => {
		listRuns.mockResolvedValue({ runs: [{ name: "R1", status: "Completed" }], total: 30 });
		getRun.mockResolvedValue({
			name: "WFR-00012",
			status: "Failed",
			node_runs: [],
			error_message: "boom",
		});
		const w = mount(RunHistoryPanel, {
			props: { workflowId: "WF-1", focusRunName: "WFR-00012" },
		});
		await flushPromises();
		expect(getRun).toHaveBeenCalledWith("WFR-00012");
		expect(w.findAll(".run-card")[0].text()).toContain("boom");
	});

	it("says so and expands nothing when a focused run cannot be loaded", async () => {
		listRuns.mockResolvedValue({ runs: [{ name: "R1", status: "Completed" }], total: 1 });
		getRun.mockRejectedValue(
			Object.assign(new Error("gone"), { userMessage: "Run not found" }),
		);
		const w = mount(RunHistoryPanel, {
			props: { workflowId: "WF-1", focusRunName: "WFR-00012" },
		});
		await flushPromises();
		expect(showError).toHaveBeenCalledTimes(1);
		expect(showError.mock.calls[0][0]).toContain("WFR-00012");
		expect(showError.mock.calls[0][0]).toContain("Run not found");
		expect(w.findAllComponents(RunCard).every((c) => c.props("isExpanded") === false)).toBe(
			true,
		);
	});
});
