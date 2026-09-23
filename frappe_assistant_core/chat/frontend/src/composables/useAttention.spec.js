import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";

const listRuns = vi.fn();
const listWorkflows = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		workflows: {
			listRuns: (...a) => listRuns(...a),
			list: (...a) => listWorkflows(...a),
		},
	},
}));

import { useAttention, FAILURE_WINDOW_MS } from "./useAttention";
import { useUserStore } from "@/stores/userStore";

function isoMinutesAgo(mins) {
	return new Date(Date.now() - mins * 60000).toISOString().replace("T", " ").slice(0, 19);
}

// The composable filters against the ARCHIVED set (fail-open). By default the
// archived set is empty, so nothing is filtered out.
function archived(names) {
	listWorkflows.mockResolvedValue({ workflows: names.map((name) => ({ name })) });
}

describe("useAttention", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		listRuns.mockReset();
		listWorkflows.mockReset();
		localStorage.clear();
		archived([]);
	});

	it("stays null when workflows capability is off", async () => {
		useUserStore().workflowsEnabled = false;
		const { attention, loadAttention } = useAttention();
		await loadAttention();
		expect(listRuns).not.toHaveBeenCalled();
		expect(attention.value).toBeNull();
	});

	it("reports recent failures with the workflow name", async () => {
		useUserStore().workflowsEnabled = true;
		listRuns.mockResolvedValue({
			runs: [{ workflow: "Invoice follow-up", status: "Failed", started_at: isoMinutesAgo(60) }],
		});
		const { attention, loadAttention } = useAttention();
		await loadAttention();
		expect(listRuns).toHaveBeenCalledWith(null, "Failed", 0, 20);
		expect(attention.value).toMatchObject({ count: 1, workflowName: "Invoice follow-up" });
	});

	it("ignores failures older than the window", async () => {
		useUserStore().workflowsEnabled = true;
		listRuns.mockResolvedValue({
			runs: [{ workflow: "Old", status: "Failed", started_at: isoMinutesAgo(60 * 30) }],
		});
		const { attention, loadAttention } = useAttention();
		await loadAttention();
		expect(attention.value).toBeNull();
	});

	it("is fail-silent on API errors", async () => {
		useUserStore().workflowsEnabled = true;
		listRuns.mockRejectedValue(new Error("boom"));
		const { attention, loadAttention } = useAttention();
		await loadAttention();
		expect(attention.value).toBeNull();
	});

	it("excludes failures whose workflow is archived (soft-deleted)", async () => {
		useUserStore().workflowsEnabled = true;
		listRuns.mockResolvedValue({
			runs: [{ workflow: "Deleted WF", status: "Failed", started_at: isoMinutesAgo(30) }],
		});
		archived(["Deleted WF"]);
		const { attention, loadAttention } = useAttention();
		await loadAttention();
		expect(listWorkflows).toHaveBeenCalledWith("Archived", 0, 100);
		expect(attention.value).toBeNull();
	});

	it("counts only the still-active workflows in a mixed batch", async () => {
		useUserStore().workflowsEnabled = true;
		listRuns.mockResolvedValue({
			runs: [
				{ workflow: "A", status: "Failed", started_at: isoMinutesAgo(10) },
				{ workflow: "Deleted", status: "Failed", started_at: isoMinutesAgo(20) },
				{ workflow: "B", status: "Failed", started_at: isoMinutesAgo(30) },
			],
		});
		archived(["Deleted"]);
		const { attention, loadAttention } = useAttention();
		await loadAttention();
		expect(attention.value).toMatchObject({ count: 2, workflowName: null });
	});

	it("fails OPEN — an active workflow absent from the (paged) list is never hidden", async () => {
		// Regression guard: matching the ACTIVE set would misclassify a workflow
		// beyond page 0 as archived. We match the ARCHIVED set instead, so an
		// active workflow that appears in neither is still shown.
		useUserStore().workflowsEnabled = true;
		listRuns.mockResolvedValue({
			runs: [{ workflow: "WF-page-2", status: "Failed", started_at: isoMinutesAgo(10) }],
		});
		archived(["Some Other Archived WF"]);
		const { attention, loadAttention } = useAttention();
		await loadAttention();
		expect(attention.value).toMatchObject({ count: 1 });
	});

	it("falls back to showing failures when the archived lookup fails", async () => {
		useUserStore().workflowsEnabled = true;
		listRuns.mockResolvedValue({
			runs: [{ workflow: "A", status: "Failed", started_at: isoMinutesAgo(10) }],
		});
		listWorkflows.mockRejectedValue(new Error("offline"));
		const { attention, loadAttention } = useAttention();
		await loadAttention();
		expect(attention.value).toMatchObject({ count: 1 });
	});

	it("dismiss hides the banner and persists a watermark", async () => {
		useUserStore().workflowsEnabled = true;
		listRuns.mockResolvedValue({
			runs: [{ workflow: "A", status: "Failed", started_at: isoMinutesAgo(10) }],
		});
		const { attention, loadAttention, dismiss } = useAttention();
		await loadAttention();
		expect(attention.value).not.toBeNull();
		dismiss();
		expect(attention.value).toBeNull();
		expect(Number(localStorage.getItem("faco.attention_dismissed_ts"))).toBeGreaterThan(0);
	});

	it("dismiss still clears the banner when localStorage.setItem throws", async () => {
		useUserStore().workflowsEnabled = true;
		listRuns.mockResolvedValue({
			runs: [{ workflow: "A", status: "Failed", started_at: isoMinutesAgo(10) }],
		});
		const { attention, loadAttention, dismiss } = useAttention();
		await loadAttention();
		const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
			throw new Error("QuotaExceeded");
		});
		expect(() => dismiss()).not.toThrow();
		expect(attention.value).toBeNull();
		spy.mockRestore();
	});

	it("stays dismissed for the same failures but resurfaces on a newer one", async () => {
		useUserStore().workflowsEnabled = true;
		listRuns.mockResolvedValue({
			runs: [{ workflow: "A", status: "Failed", started_at: isoMinutesAgo(30) }],
		});
		const first = useAttention();
		await first.loadAttention();
		first.dismiss();

		const second = useAttention();
		await second.loadAttention();
		expect(second.attention.value).toBeNull();

		listRuns.mockResolvedValue({
			runs: [
				{ workflow: "A", status: "Failed", started_at: isoMinutesAgo(30) },
				{ workflow: "B", status: "Failed", started_at: isoMinutesAgo(1) },
			],
		});
		const third = useAttention();
		await third.loadAttention();
		expect(third.attention.value).toMatchObject({ count: 1, workflowName: "B" });
	});

	it("does not fetch the archived list when there are no in-window failures", async () => {
		useUserStore().workflowsEnabled = true;
		listRuns.mockResolvedValue({
			runs: [{ workflow: "Old", status: "Failed", started_at: isoMinutesAgo(60 * 30) }],
		});
		const { loadAttention } = useAttention();
		await loadAttention();
		expect(listWorkflows).not.toHaveBeenCalled();
	});

	it("window is 24h", () => {
		expect(FAILURE_WINDOW_MS).toBe(24 * 60 * 60 * 1000);
	});
});
