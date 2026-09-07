import {
	generateNodeId,
	getDefaultLabel,
	getDefaultConfig,
} from "@/components/workflows/graphUtils";

/**
 * Canvas interaction for the builder: Vue Flow's own change events plus the
 * add/duplicate/connect paths the palette and keyboard drive.
 *
 * Every mutation is gated on `canEdit` — a read-only viewer's canvas must not
 * quietly autosave into a wall of 403s.
 *
 * @param {object} deps - { nodes, edges, selectedNode, canEdit, scheduleAutoSave,
 *                          project, canvasAreaRef }
 */
export function useBuilderGraph({
	nodes,
	edges,
	selectedNode,
	canEdit,
	scheduleAutoSave,
	project,
	canvasAreaRef,
}) {
	function onNodesChange(changes) {
		let needsSave = false;
		for (const change of changes) {
			if (change.type === "position" && change.position) {
				const node = nodes.value.find((n) => n.id === change.id);
				if (node) {
					node.position = change.position;
					needsSave = true;
				}
			}
			if (change.type === "remove") {
				if (!canEdit.value) continue;
				nodes.value = nodes.value.filter((n) => n.id !== change.id);
				edges.value = edges.value.filter(
					(e) => e.source !== change.id && e.target !== change.id
				);
				if (selectedNode.value?.id === change.id) selectedNode.value = null;
				needsSave = true;
			}
			if (change.type === "dimensions" && change.dimensions) {
				const node = nodes.value.find((n) => n.id === change.id);
				if (node) node.dimensions = change.dimensions;
			}
			if (change.type === "select") {
				const node = nodes.value.find((n) => n.id === change.id);
				if (node) node.selected = change.selected;
			}
		}
		if (needsSave) scheduleAutoSave();
	}

	function onEdgesChange(changes) {
		let needsSave = false;
		for (const change of changes) {
			if (change.type === "remove") {
				if (!canEdit.value) continue;
				edges.value = edges.value.filter((e) => e.id !== change.id);
				needsSave = true;
			}
			if (change.type === "select") {
				const edge = edges.value.find((e) => e.id === change.id);
				if (edge) edge.selected = change.selected;
			}
		}
		if (needsSave) scheduleAutoSave();
	}

	/** Reject connections the engine could never execute.
	 *
	 * Vue Flow runs this over EVERY edge as it ingests them, not only over a
	 * connection being dragged (createGraphEdges drops an edge this returns
	 * false for). An edge under ingestion is already in `edges`, so a
	 * duplicate check that does not exclude the edge itself matches itself and
	 * every edge in the graph disappears on load — and a freshly drawn one
	 * vanishes the moment onConnect adds it and Vue Flow re-ingests.
	 *
	 * A dragged connection has no id, so `e.id !== connection.id` still
	 * catches real duplicates there.
	 */
	function isValidConnection(connection) {
		const { source, target } = connection || {};
		if (!source || !target || source === target) return false;
		const sourceNode = nodes.value.find((n) => n.id === source);
		const targetNode = nodes.value.find((n) => n.id === target);
		if (!sourceNode || !targetNode) return false;
		if (sourceNode.type === "workflow-output") return false;
		if (targetNode.type === "workflow-input") return false;
		return !edges.value.some(
			(e) =>
				e.id !== connection.id &&
				e.source === source &&
				e.target === target &&
				(e.sourceHandle || "") === (connection.sourceHandle || "")
		);
	}

	function onConnect(params) {
		if (!canEdit.value) return;
		edges.value = [
			...edges.value,
			{
				id: `e-${params.source}-${params.target}-${Date.now()}`,
				source: params.source,
				target: params.target,
				sourceHandle: params.sourceHandle || undefined,
				label: params.sourceHandle || "",
				type: "smoothstep",
				// Must match graphJsonToVueFlow, or an edge you just drew looks
				// different from the same edge after a reload.
				markerEnd: "arrowclosed",
				animated: false,
				selectable: true,
			},
		];
		scheduleAutoSave();
	}

	function addNode(node) {
		nodes.value = [...nodes.value, node];
		selectedNode.value = node;
		scheduleAutoSave();
	}

	/** Click-to-add from the palette — also the only path that works on touch. */
	function addNodeOfType(type) {
		if (!canEdit.value) return;
		const bounds = canvasAreaRef.value?.getBoundingClientRect();
		const position = project({
			x: (bounds?.width || 800) / 2,
			y: (bounds?.height || 600) / 2,
		});
		addNode({
			id: generateNodeId(type),
			type,
			position: { x: Math.round(position.x), y: Math.round(position.y) },
			data: { label: getDefaultLabel(type), config: getDefaultConfig(type) },
		});
	}

	/** Selection follows the click: a node opens its config, the pane closes it. */
	function onNodeClick({ node }) {
		selectedNode.value = node;
	}

	function onPaneClick() {
		selectedNode.value = null;
	}

	function duplicateSelectedNode() {
		const source = selectedNode.value;
		if (!canEdit.value || !source) return;
		addNode({
			id: generateNodeId(source.type),
			type: source.type,
			position: { x: source.position.x + 40, y: source.position.y + 40 },
			data: JSON.parse(JSON.stringify(source.data || {})),
		});
	}

	return {
		onNodesChange,
		onEdgesChange,
		onConnect,
		isValidConnection,
		onNodeClick,
		onPaneClick,
		addNodeOfType,
		duplicateSelectedNode,
	};
}
