import { describe, it, expect } from "vitest";
import { ref } from "vue";
import { useRunNodeStatus } from "@/composables/useRunNodeStatus";

function setup(run, running = true) {
	return useRunNodeStatus(ref(run), ref(running));
}

describe("useRunNodeStatus", () => {
	it("is empty with no run", () => {
		const { statusByNode, hasRunState } = setup(null);
		expect(statusByNode.value.size).toBe(0);
		expect(hasRunState.value).toBe(false);
	});

	it("maps every node run onto a canvas class", () => {
		const { nodeClass } = setup({
			node_runs: [
				{ node_id: "agent_1", status: "Completed" },
				{ node_id: "agent_2", status: "Failed" },
				{ node_id: "agent_3", status: "Running" },
			],
		});
		expect(nodeClass("agent_1")).toBe("run-completed");
		expect(nodeClass("agent_2")).toBe("run-failed");
		expect(nodeClass("agent_3")).toBe("run-running");
		expect(nodeClass("unknown")).toBe("");
	});

	it("marks current_node running before its node run row exists", () => {
		const { nodeClass } = setup({ node_runs: [], current_node: "agent_1" });
		expect(nodeClass("agent_1")).toBe("run-running");
	});

	it("does not invent a running node once the run has stopped", () => {
		const { nodeClass } = setup({ node_runs: [], current_node: "agent_1" }, false);
		expect(nodeClass("agent_1")).toBe("");
	});

	it("animates only the edge feeding the node being worked on", () => {
		const { isEdgeAnimated } = setup({
			node_runs: [
				{ node_id: "a", status: "Completed" },
				{ node_id: "b", status: "Running" },
				{ node_id: "c", status: "Pending" },
			],
		});
		expect(isEdgeAnimated({ source: "a", target: "b" })).toBe(true);
		expect(isEdgeAnimated({ source: "b", target: "c" })).toBe(false);
	});

	it("stops animating when the run is over", () => {
		const { isEdgeAnimated } = setup(
			{
				node_runs: [
					{ node_id: "a", status: "Completed" },
					{ node_id: "b", status: "Running" },
				],
			},
			false
		);
		expect(isEdgeAnimated({ source: "a", target: "b" })).toBe(false);
	});
});
