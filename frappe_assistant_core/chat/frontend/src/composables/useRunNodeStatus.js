import { computed, watch } from "vue";

/** Node-run status → the canvas class that paints it. */
const STATUS_CLASS = {
	Running: "run-running",
	Completed: "run-completed",
	Failed: "run-failed",
	Skipped: "run-skipped",
	Pending: "run-pending",
};

/**
 * Live canvas state for the run the store is polling.
 *
 * Reads the run's node_runs (durable, one row per node) plus `current_node`
 * (the row the engine is on right now, which may not have a node run yet), and
 * exposes them as a Map the builder binds to node classes and edge `animated`.
 *
 * @param {import("vue").Ref} currentRun - workflowStore.currentRun
 * @param {import("vue").Ref} isRunning  - workflowStore.isRunning
 * @param {object} [canvas] - { nodes, edges } refs to paint; omit to only read.
 */
export function useRunNodeStatus(currentRun, isRunning, canvas = null) {
	const statusByNode = computed(() => {
		const map = new Map();
		const run = currentRun.value;
		if (!run) return map;

		for (const nodeRun of run.node_runs || []) {
			if (nodeRun?.node_id) map.set(nodeRun.node_id, nodeRun.status || "Pending");
		}

		// The engine writes current_node before the node run row exists.
		if (isRunning.value && run.current_node && !map.has(run.current_node)) {
			map.set(run.current_node, "Running");
		}
		return map;
	});

	const hasRunState = computed(() => statusByNode.value.size > 0);

	function nodeClass(nodeId) {
		return STATUS_CLASS[statusByNode.value.get(nodeId)] || "";
	}

	/** An edge animates while its source has finished and its target is working. */
	function isEdgeAnimated(edge) {
		if (!isRunning.value || !edge) return false;
		const source = statusByNode.value.get(edge.source);
		const target = statusByNode.value.get(edge.target);
		return source === "Completed" && target === "Running";
	}

	// Written onto the node/edge objects themselves: the serializer ignores both
	// keys, and copying into a derived array would strand drag positions.
	if (canvas) {
		watch(
			[currentRun, isRunning, canvas.nodes, canvas.edges],
			() => {
				for (const node of canvas.nodes.value) node.class = nodeClass(node.id);
				for (const edge of canvas.edges.value) edge.animated = isEdgeAnimated(edge);
			},
			{ deep: false }
		);
	}

	return { statusByNode, hasRunState, nodeClass, isEdgeAnimated };
}
