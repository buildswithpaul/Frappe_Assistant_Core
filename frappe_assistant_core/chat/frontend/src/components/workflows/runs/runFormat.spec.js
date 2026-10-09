import { describe, it, expect } from "vitest";
import {
	parseSkippedActions,
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
