import { describe, it, expect } from "vitest";
import { ref } from "vue";
import { useRunNodeStatus } from "./useRunNodeStatus";

describe("useRunNodeStatus", () => {
	it("marks the node whose write was skipped", () => {
		const run = ref({
			status: "Completed",
			node_runs: [{ node_id: "a", status: "Completed" }],
			skipped_actions_detail: JSON.stringify([{ node_id: "a", tool: "send_email", reason: "x" }]),
		});
		const { nodeClass } = useRunNodeStatus(run, ref(false));
		expect(nodeClass("a")).toBe("run-completed run-skipped-action");
	});

	it("paints a failed node", () => {
		const run = ref({ node_runs: [{ node_id: "b", status: "Failed" }] });
		expect(useRunNodeStatus(run, ref(false)).nodeClass("b")).toBe("run-failed");
	});
});
