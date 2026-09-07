import {
	generateNodeId,
	getDefaultLabel,
	getDefaultConfig,
} from "@/components/workflows/graphUtils";

/**
 * Graph-mutation actions driven by the palette/config-panel (not by Vue Flow's
 * own change events — those remain in the parent, per D5b's risk note about
 * `onNodesChange`/`onEdgesChange` coupling).
 *
 * Handles:
 *  - onDrop: drag-from-palette → create node at projected pane coordinates
 *  - handleNodeUpdate: config-panel label/config edits
 *  - handleDeleteNode: config-panel delete (also removes incident edges)
 *
 * All reactive targets are parent-owned and passed in; this composable only
 * reads + mutates what it's given. `project` is passed in (not obtained via
 * useVueFlow() here) so the parent's single `useVueFlow()` call remains the
 * sole point of coupling to Vue Flow's imperative API.
 *
 * @param {object} deps - { nodes, edges, selectedNode, scheduleAutoSave, project }
 */
export function useWorkflowGraphActions({
	nodes,
	edges,
	selectedNode,
	scheduleAutoSave,
	project,
}) {
	function onDrop(event) {
		const type = event.dataTransfer.getData("application/workflow-node-type");
		if (!type) return;

		const canvasEl = event.currentTarget.querySelector(".vue-flow__pane");
		if (!canvasEl) return;

		const bounds = canvasEl.getBoundingClientRect();
		const position = project({
			x: event.clientX - bounds.left,
			y: event.clientY - bounds.top,
		});

		const newNode = {
			id: generateNodeId(type),
			type,
			position: { x: Math.round(position.x), y: Math.round(position.y) },
			data: {
				label: getDefaultLabel(type),
				config: getDefaultConfig(type),
			},
		};

		nodes.value = [...nodes.value, newNode];
		selectedNode.value = newNode;
		scheduleAutoSave();
	}

	function handleNodeUpdate(nodeId, updates) {
		const node = nodes.value.find((n) => n.id === nodeId);
		if (!node) return;

		// Accumulate all updates in a single spread to avoid sequential overwrites
		node.data = {
			...node.data,
			...(updates.label !== undefined ? { label: updates.label } : {}),
			...(updates.config !== undefined ? { config: updates.config } : {}),
		};

		// Refresh selected node reference so config panel stays in sync
		if (selectedNode.value?.id === nodeId) {
			selectedNode.value = { ...node };
		}

		scheduleAutoSave();
	}

	function handleDeleteNode(nodeId) {
		nodes.value = nodes.value.filter((n) => n.id !== nodeId);
		edges.value = edges.value.filter((e) => e.source !== nodeId && e.target !== nodeId);
		if (selectedNode.value?.id === nodeId) selectedNode.value = null;
		scheduleAutoSave();
	}

	return { onDrop, handleNodeUpdate, handleDeleteNode };
}
