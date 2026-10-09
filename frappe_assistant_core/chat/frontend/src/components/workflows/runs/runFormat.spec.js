import { describe, it, expect } from "vitest";
import {
	loopSummary,
	parseSkippedActions,
	partialOutput,
	runBadge,
	skippedCount,
	statusClass,
	triggerLabel,
} from "./runFormat";

describe("runFormat", () => {
	it("styles Timed Out", () => {
		expect(statusClass("Timed Out")).toBe("badge-timeout");
	});

	it("labels document-event runs", () => {
		expect(triggerLabel("doc_event")).toBe("Event");
		expect(triggerLabel("scheduled")).toBe("Scheduled");
	});

	it("reads skipped actions from a JSON string, a list, or nothing", () => {
		const detail = [{ node_id: "a", tool: "create_document", reason: "not pre-approved" }];
		expect(parseSkippedActions({ skipped_actions_detail: JSON.stringify(detail) })).toEqual(
			detail
		);
		expect(parseSkippedActions({ skipped_actions_detail: detail })).toEqual(detail);
		expect(parseSkippedActions({ skipped_actions_detail: "{oops" })).toEqual([]);
		expect(parseSkippedActions({ skipped_actions_detail: null })).toEqual([]);
		expect(parseSkippedActions({})).toEqual([]);
		expect(parseSkippedActions({ skipped_actions_detail: '{"not":"a list"}' })).toEqual([]);
	});

	it("prefers the server's count and falls back to the parsed list", () => {
		expect(skippedCount({ skipped_actions: 3 })).toBe(3);
		expect(skippedCount({ skipped_actions_detail: '[{"tool":"x"}]' })).toBe(1);
		expect(skippedCount({ skipped_actions: "junk" })).toBe(0);
	});

	it("says Completed · N actions skipped in amber", () => {
		expect(runBadge({ status: "Completed", skipped_actions: 2 })).toEqual({
			text: "Completed · 2 actions skipped",
			cls: "badge-warning",
		});
		expect(runBadge({ status: "Completed", skipped_actions: 1 }).text).toBe(
			"Completed · 1 action skipped"
		);
		expect(runBadge({ status: "Completed" })).toEqual({
			text: "Completed",
			cls: "badge-success",
		});
		expect(runBadge({ status: "Failed", skipped_actions: 1 }).cls).toBe("badge-danger");
	});
});

describe("partialOutput", () => {
	it("offers the last finished step's output on a failed run", () => {
		const run = {
			status: "Failed",
			output_data: "",
			node_runs: [
				{ node_id: "a", node_label: "Fetch AR", status: "Completed", output_text: "rows" },
				{ node_id: "b", node_label: "Rank", status: "Completed", output_text: "ranked list" },
				{ node_id: "c", node_label: "Email", status: "Failed", output_text: "" },
			],
		};
		expect(partialOutput(run)).toEqual({ label: "Rank", text: "ranked list", truncated: false });
	});

	it("flags text the server or the helper cut at 10,000 characters", () => {
		const long = "x".repeat(10050);
		const run = { status: "Failed", node_runs: [{ node_id: "a", status: "Completed", output_text: long }] };
		const out = partialOutput(run);
		expect(out.text).toHaveLength(10000);
		expect(out.truncated).toBe(true);
		const flagged = {
			status: "Failed",
			node_runs: [{ node_id: "a", status: "Completed", output_text: "short", output_text_truncated: 1 }],
		};
		expect(partialOutput(flagged).truncated).toBe(true);
	});

	it("is null for a completed run or one with nothing finished", () => {
		expect(partialOutput({ status: "Completed", output_data: "x", node_runs: [] })).toBe(null);
		expect(partialOutput({ status: "Failed", node_runs: [{ status: "Failed" }] })).toBe(null);
	});
});

describe("loopSummary", () => {
	it("reads a loop node's counts", () => {
		expect(loopSummary('{"results":[],"processed":0,"failed":0,"skipped_over_limit":0}')).toEqual({
			processed: 0,
			failed: 0,
			skipped: 0,
		});
		expect(loopSummary("plain text")).toBe(null);
	});
});
