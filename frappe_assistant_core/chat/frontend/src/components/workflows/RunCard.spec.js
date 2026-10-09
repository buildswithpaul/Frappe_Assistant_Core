import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import RunCard from "./RunCard.vue";

const failedRun = {
	name: "R1",
	status: "Failed",
	trigger_type: "doc_event",
	error_message: "Report Accounts Receivable needs the filter: company. ".repeat(4),
	total_nodes: 3,
	completed_nodes: 1,
};

describe("RunCard", () => {
	it("styles a timed-out run", () => {
		const w = mount(RunCard, { props: { run: { name: "R2", status: "Timed Out" } } });
		expect(w.get(".status-badge").classes()).toContain("badge-timeout");
	});

	it("labels an event-triggered run", () => {
		const w = mount(RunCard, { props: { run: failedRun } });
		expect(w.text()).toContain("Event");
	});

	it("shows the full error once expanded, even when nodes ran", () => {
		const w = mount(RunCard, {
			props: {
				run: failedRun,
				isExpanded: true,
				expandedData: {
					...failedRun,
					node_runs: [{ node_id: "a", node_label: "Fetch", status: "Failed" }],
				},
			},
		});
		expect(w.get(".detail-error-full").text()).toBe(failedRun.error_message.trim());
	});

	it("lists skipped actions by node label", () => {
		const run = {
			name: "R3",
			status: "Completed",
			skipped_actions: 1,
			skipped_actions_detail: JSON.stringify([
				{ node_id: "a", tool: "send_email", reason: "Not pre-approved" },
			]),
		};
		const w = mount(RunCard, {
			props: {
				run,
				isExpanded: true,
				expandedData: {
					...run,
					node_runs: [{ node_id: "a", node_label: "Notify", status: "Completed" }],
				},
			},
		});
		expect(w.get(".status-badge").text()).toBe("Completed · 1 action skipped");
		expect(w.text()).toContain("Notify");
		expect(w.text()).toContain("send_email");
		expect(w.text()).toContain("Not pre-approved");
	});

	it("survives a malformed skipped list", () => {
		const run = { name: "R4", status: "Completed", skipped_actions_detail: "{oops" };
		const w = mount(RunCard, {
			props: { run, isExpanded: true, expandedData: { ...run, node_runs: [] } },
		});
		expect(w.get(".status-badge").text()).toBe("Completed");
	});
});
