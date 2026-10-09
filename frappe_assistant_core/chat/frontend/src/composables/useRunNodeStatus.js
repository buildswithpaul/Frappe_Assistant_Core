import { computed, watch } from "vue";
import { parseSkippedActions } from "@/components/workflows/runs/runFormat";

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
 * @param {object} [canvas] - { nodes, edges, sync } to paint; omit to only read. `sync`
 *   ({ updateNode, updateEdge }) carries each write to Vue Flow's own node copies.
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

	const skippedNodes = computed(
		() => new Set(parseSkippedActions(currentRun.value).map((s) => s.node_id).filter(Boolean))
	);

	function nodeClass(nodeId) {
		const base = STATUS_CLASS[statusByNode.value.get(nodeId)] || "";
		return skippedNodes.value.has(nodeId) ? `${base} run-skipped-action`.trim() : base;
	}

	/** An edge animates while its source has finished and its target is working. */
	function isEdgeAnimated(edge) {
		if (!isRunning.value || !edge) return false;
		const source = statusByNode.value.get(edge.source);
		const target = statusByNode.value.get(edge.target);
		return source === "Completed" && target === "Running";
	}

	// Written onto the builder's node/edge objects (the serializer ignores both
	// keys, and copying into a derived array would strand drag positions) AND
	// through `sync`: the canvas is bound one-way and renders Vue Flow's own
	// copies, so a write to the builder's objects alone never reaches it.
	if (canvas) {
		watch(
			[currentRun, isRunning, canvas.nodes, canvas.edges],
			() => {
				for (const node of canvas.nodes.value) {
					node.class = nodeClass(node.id);
					canvas.sync?.updateNode(node.id, { class: node.class });
				}
				for (const edge of canvas.edges.value) {
					edge.animated = isEdgeAnimated(edge);
					canvas.sync?.updateEdge(edge.id, { animated: edge.animated });
				}
			},
			{ deep: false }
		);
	}

	return { statusByNode, hasRunState, nodeClass, isEdgeAnimated };
}
