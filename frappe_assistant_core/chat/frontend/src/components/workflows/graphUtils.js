/**
 * Utility functions for converting between backend graph JSON and Vue Flow format.
 *
 * Vue Flow reserves the type names "input", "output", and "default" for its
 * built-in node wrappers. We prefix ours with "workflow-" to avoid collision,
 * mapping back to the backend names on serialization.
 */

// Backend type ↔ Vue Flow type (avoids Vue Flow reserved names)
const BACKEND_TO_VF = { input: "workflow-input", output: "workflow-output" };
const VF_TO_BACKEND = { "workflow-input": "input", "workflow-output": "output" };

function toVfType(backendType) {
	return BACKEND_TO_VF[backendType] || backendType;
}
function toBackendType(vfType) {
	return VF_TO_BACKEND[vfType] || vfType;
}

/**
 * Convert backend graph JSON to Vue Flow nodes and edges.
 */
export function graphJsonToVueFlow(graphJson) {
	if (!graphJson) return { nodes: [], edges: [], globalSettings: {} };

	const graph = typeof graphJson === "string" ? JSON.parse(graphJson) : graphJson;

	const nodes = (graph.nodes || []).map((n) => ({
		id: n.id,
		type: toVfType(n.type),
		position: n.position || { x: 0, y: 0 },
		data: {
			label: n.label || n.id,
			config: n.config || {},
		},
	}));

	const edges = (graph.edges || []).map((e, i) => ({
		id: e.id || `e-${e.source}-${e.target}-${i}`,
		source: e.source,
		target: e.target,
		sourceHandle: e.condition || undefined,
		label: e.condition || "",
		type: "smoothstep",
		// A DAG is unreadable without direction, and two nodes side by side
		// give the eye no other cue which way the data flows.
		markerEnd: "arrowclosed",
		animated: false,
		selectable: true,
	}));

	return {
		nodes,
		edges,
		globalSettings: graph.global_settings || {},
	};
}

/**
 * Convert Vue Flow state back to backend graph JSON string.
 */
export function vueFlowToGraphJson(nodes, edges, globalSettings = {}) {
	return JSON.stringify({
		version: "1.0",
		nodes: nodes.map((n) => ({
			id: n.id,
			type: toBackendType(n.type),
			label: n.data?.label || n.id,
			position: {
				x: Math.round(n.position.x),
				y: Math.round(n.position.y),
			},
			config: n.data?.config || {},
		})),
		edges: edges.map((e) => {
			const edge = {
				id: e.id,
				source: e.source,
				target: e.target,
			};
			if (e.sourceHandle) edge.condition = e.sourceHandle;
			else if (e.label) edge.condition = e.label;
			return edge;
		}),
		global_settings: globalSettings,
	});
}

/**
 * Generate a unique node ID using the backend type name.
 */
export function generateNodeId(type) {
	const backendType = toBackendType(type);
	return `${backendType}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
}

/**
 * Get default label for a node type (accepts both Vue Flow and backend names).
 */
export function getDefaultLabel(type) {
	const labels = {
		"workflow-input": "Input",
		"workflow-output": "Output",
		input: "Input",
		output: "Output",
		agent: "Task",
		condition: "Condition",
		transform: "Transform",
	};
	return labels[type] || type;
}

/**
 * Get default config for a node type (accepts both Vue Flow and backend names).
 */
export function getDefaultConfig(type) {
	const bt = toBackendType(type);
	switch (bt) {
		case "input":
			return { input_schema: {} };
		case "output":
			return { output_template: "" };
		case "agent":
			// use_memory is on for new nodes and absent (falsy) on existing
			// graphs, so no saved workflow silently changes behaviour.
			return {
				system_prompt: "",
				model_id: "",
				user_id: "",
				mcp_servers: [],
				tool_directives: [],
				use_memory: true,
			};
		case "condition":
			return { condition_field: "", condition_operator: "equals", condition_value: "" };
		case "transform":
			return { transform_template: "{{ input }}" };
		default:
			return {};
	}
}

/**
 * Validate graph structure on the frontend (fast, no backend call).
 * Returns { valid: boolean, errors: string[] }.
 */
export function validateGraph(nodes, edges) {
	const errors = [];

	if (!nodes.length) {
		return { valid: false, errors: ["Workflow must have at least one node"] };
	}

	// Check for entry points
	const targetIds = new Set(edges.map((e) => e.target));
	const inputNodes = nodes.filter((n) => n.type === "workflow-input" || n.type === "input");
	const entryNodes = nodes.filter((n) => !targetIds.has(n.id));
	if (!inputNodes.length && !entryNodes.length) {
		errors.push(
			"Workflow must have at least one entry point (input node or node with no incoming edges)"
		);
	}

	// Check agent nodes have system prompts
	for (const node of nodes) {
		const bt = toBackendType(node.type);
		if (bt === "agent" && !node.data?.config?.system_prompt) {
			errors.push(`Task "${node.data?.label || node.id}" is missing a system prompt`);
		}
	}

	// Check for self-loops
	for (const edge of edges) {
		if (edge.source === edge.target) {
			errors.push(`Self-loop detected: node "${edge.source}" connects to itself`);
		}
	}

	// Check for orphaned nodes (unreachable from entry points)
	const adjacency = {};
	for (const edge of edges) {
		if (!adjacency[edge.source]) adjacency[edge.source] = [];
		adjacency[edge.source].push(edge.target);
	}

	const reachable = new Set();
	const entryIds = inputNodes.length ? inputNodes.map((n) => n.id) : entryNodes.map((n) => n.id);

	const stack = [...entryIds];
	while (stack.length) {
		const id = stack.pop();
		if (reachable.has(id)) continue;
		reachable.add(id);
		for (const neighbor of adjacency[id] || []) {
			stack.push(neighbor);
		}
	}

	const nodeIds = new Set(nodes.map((n) => n.id));
	const unreachable = [...nodeIds].filter((id) => !reachable.has(id));
	if (unreachable.length) {
		errors.push(`Unreachable nodes: ${unreachable.join(", ")}`);
	}

	return { valid: errors.length === 0, errors };
}

/**
 * Condition operators offered by the builder.
 *
 * Must stay equal to VALID_CONDITION_OPERATORS in
 * assistant_runtime_workflows/engine/validation.py — an operator the SPA
 * offers but the validator rejects fails only at save time.
 */
export const CONDITION_OPERATORS = [
	{ value: "equals", label: "Equals" },
	{ value: "not_equals", label: "Not Equals" },
	{ value: "contains", label: "Contains" },
	{ value: "not_contains", label: "Not Contains" },
	{ value: "greater_than", label: "Greater Than" },
	{ value: "less_than", label: "Less Than" },
	{ value: "is_truthy", label: "Is Truthy" },
	{ value: "regex", label: "Regex Match" },
];

/**
 * Node type metadata (icons, colors, descriptions).
 * Uses Vue Flow type names for direct use in the canvas.
 */
export const NODE_TYPES = [
	{
		type: "workflow-input",
		label: "Input",
		description: "Workflow entry point",
		color: "var(--ql-success)",
		iconPath: "M13 9l3 3m0 0l-3 3m3-3H8m13 0a9 9 0 11-18 0 9 9 0 0118 0z",
	},
	{
		type: "agent",
		label: "Task",
		description: "AI task with tools",
		color: "var(--ql-accent)",
		iconPath:
			"M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
	},
	{
		type: "condition",
		label: "Condition",
		description: "Branch based on rules",
		color: "var(--ql-warning)",
		iconPath: "M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4",
	},
	{
		type: "transform",
		label: "Transform",
		description: "Reshape data with templates",
		color: "#8b5cf6",
		iconPath: "M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4",
	},
	{
		type: "workflow-output",
		label: "Output",
		description: "Workflow result",
		color: "var(--ql-danger)",
		iconPath:
			"M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9",
	},
];
