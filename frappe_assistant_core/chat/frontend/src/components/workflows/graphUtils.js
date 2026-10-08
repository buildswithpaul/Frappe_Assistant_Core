/**
 * Utility functions for converting between backend graph JSON and Vue Flow format.
 *
 * Vue Flow reserves the type names "input", "output", and "default" for its
 * built-in node wrappers. We prefix ours with "workflow-" to avoid collision,
 * mapping back to the backend names on serialization.
 */

import { __ } from "@/utils/i18n";

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
		tool: "Tool",
		loop: "For each",
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
				max_tool_calls: 25,
			};
		case "condition":
			return { condition_field: "", condition_operator: "equals", condition_value: "" };
		case "transform":
			return { transform_template: "{{ input }}" };
		case "tool":
			return { tool_name: "", server: "", arguments: {}, max_rows: 200, output: "table" };
		case "loop":
			// The inline agent's keys sit flat in the loop config, the same
			// shape an agent node uses, so AgentConfig edits them unchanged.
			return {
				items_path: "rows",
				max_items: 50,
				concurrency: 3,
				stop_after_failures: 3,
				system_prompt: "",
				model_id: "",
				user_id: "",
				mcp_servers: [],
				tool_directives: [],
				use_memory: false,
				max_tool_calls: 25,
			};
		default:
			return {};
	}
}

/** Engine limits (agent_guards.py, tool_node.py, loop_node.py). The engine clamps too; this keeps the form honest. */
export const NODE_LIMITS = {
	tool: { max_rows: { min: 1, max: 2000, default: 200 } },
	loop: {
		max_items: { min: 1, max: 500, default: 50 },
		concurrency: { min: 1, max: 5, default: 3 },
		stop_after_failures: { min: 1, max: 500, default: 3 },
	},
	agent: {
		max_tool_calls: { min: 1, max: 100, default: 25 },
		timeout_seconds: { min: 30, max: 3600 },
	},
};

export function clampInt(value, { min, max, default: fallback } = {}) {
	if (value === "" || value === null || value === undefined) return fallback;
	const n = Math.round(Number(value));
	if (!Number.isFinite(n)) return fallback;
	return Math.min(max, Math.max(min, n));
}

/**
 * Validate graph structure on the frontend (fast, no backend call).
 *
 * Every problem carries the node it belongs to, so the canvas can mark it, and
 * names that node by its label: ids like agent_1712... mean nothing to a reader.
 * Returns { valid, errors: string[], issues: [{ nodeId, message }] }.
 */
export function validateGraph(nodes, edges) {
	const issues = [];
	const add = (nodeId, message) => issues.push({ nodeId, message });
	const labelOf = (n) => n.data?.label || n.id;
	const result = () => ({
		valid: issues.length === 0,
		errors: issues.map((i) => i.message),
		issues,
	});

	if (!nodes.length) {
		add(null, __("Workflow must have at least one node"));
		return result();
	}

	const targetIds = new Set(edges.map((e) => e.target));
	const inputNodes = nodes.filter((n) => n.type === "workflow-input" || n.type === "input");
	const entryNodes = nodes.filter((n) => !targetIds.has(n.id));
	if (!inputNodes.length && !entryNodes.length) {
		add(
			null,
			__(
				"Workflow must have at least one entry point (input node or node with no incoming edges)"
			)
		);
	}

	for (const n of nodes) {
		const bt = toBackendType(n.type);
		const config = n.data?.config || {};
		if (bt === "agent" && !config.system_prompt) {
			add(n.id, __('Task "{0}" is missing a system prompt', [labelOf(n)]));
		}
		if (bt === "tool" && !config.tool_name) {
			add(n.id, __('Tool step "{0}" has no tool selected', [labelOf(n)]));
		}
		if (bt === "loop" && !config.system_prompt) {
			add(n.id, __('"{0}" has no instructions for each item', [labelOf(n)]));
		}
	}

	const byId = new Map(nodes.map((n) => [n.id, n]));
	for (const edge of edges) {
		if (edge.source === edge.target) {
			const n = byId.get(edge.source);
			add(edge.source, __('"{0}" connects to itself', [n ? labelOf(n) : edge.source]));
		}
	}

	const adjacency = {};
	for (const edge of edges) {
		(adjacency[edge.source] ||= []).push(edge.target);
	}
	const reachable = new Set();
	const stack = (inputNodes.length ? inputNodes : entryNodes).map((n) => n.id);
	while (stack.length) {
		const id = stack.pop();
		if (reachable.has(id)) continue;
		reachable.add(id);
		for (const next of adjacency[id] || []) stack.push(next);
	}
	for (const n of nodes) {
		if (!reachable.has(n.id)) add(n.id, __('"{0}" is not connected to the start', [labelOf(n)]));
	}

	return result();
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
		type: "tool",
		label: "Tool",
		description: "Call one tool directly, no AI, no credits",
		color: "var(--ql-accent)",
		iconPath:
			"M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085",
	},
	{
		type: "loop",
		label: "For each",
		description: "Run a task once per item in a list",
		color: "var(--ql-text-secondary)",
		iconPath:
			"M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99",
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
