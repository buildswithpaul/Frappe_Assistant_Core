/**
 * A template's graph as numbered stages for reading, not editing.
 *
 * A step's stage is its longest path from the start, so a step that waits for
 * two others is listed after both. Steps in the same stage run side by side.
 */

import { __ } from "@/utils/i18n";

const TOOL_KINDS = {
	generate_report: () => __("Runs a report"),
	list_documents: () => __("Reads records"),
	get_document: () => __("Reads a record"),
	send_email: () => __("Sends an email"),
	create_document: () => __("Creates a draft"),
};

const NODE_KINDS = {
	input: () => __("Start"),
	agent: () => __("AI step"),
	transform: () => __("Prepares the data"),
	condition: () => __("Check"),
	loop: () => __("Repeats for each item"),
	output: () => __("Result"),
};

function kindOf(node) {
	if (node.type === "tool") {
		const tool = node.config?.tool_name || "";
		return TOOL_KINDS[tool]?.() || __("Uses {0}", [tool || __("a tool")]);
	}
	return NODE_KINDS[node.type]?.() || node.type;
}

function stagesOf(ids, edges) {
	const indegree = new Map(ids.map((id) => [id, 0]));
	const out = new Map(ids.map((id) => [id, []]));
	for (const e of edges) {
		if (!out.has(e.source) || !out.has(e.target) || e.source === e.target) continue;
		out.get(e.source).push(e.target);
		indegree.set(e.target, indegree.get(e.target) + 1);
	}
	const stage = new Map(ids.map((id) => [id, 0]));
	const queue = ids.filter((id) => indegree.get(id) === 0);
	const seen = new Set();
	while (queue.length) {
		const id = queue.shift();
		seen.add(id);
		for (const next of out.get(id)) {
			stage.set(next, Math.max(stage.get(next), stage.get(id) + 1));
			indegree.set(next, indegree.get(next) - 1);
			if (indegree.get(next) === 0) queue.push(next);
		}
	}
	// A cycle never reaches indegree 0; list what it holds after everything else.
	const last = Math.max(0, ...[...seen].map((id) => stage.get(id))) + 1;
	for (const id of ids) if (!seen.has(id)) stage.set(id, last);
	return stage;
}

function branchesOf(node, edges, labelOf) {
	if (node.type !== "condition") return [];
	const pick = (condition) =>
		edges.filter((e) => e.source === node.id && e.condition === condition).map((e) => labelOf(e.target));
	const yes = pick("pass");
	const no = pick("fail");
	if (!yes.length && !no.length) return [];
	return [
		yes.length ? __("If yes: {0}", [yes.join(", ")]) : __("If yes: stops here"),
		no.length ? __("If no: {0}", [no.join(", ")]) : __("If no: stops here"),
	];
}

/**
 * @param {{nodes: Array, edges: Array}} graph backend graph JSON, parsed
 * @returns {Array<{number: number, steps: Array<{key, label, kind, type, branches}>}>}
 */
export function templateStages(graph) {
	const nodes = graph.nodes || [];
	const edges = graph.edges || [];
	const ids = [...new Set(nodes.map((n) => n.id))];
	const byId = new Map(nodes.map((n) => [n.id, n]));
	const labelOf = (id) => String(byId.get(id)?.label || id);
	const stage = stagesOf(ids, edges);

	const groups = new Map();
	nodes.forEach((node, i) => {
		const s = stage.get(node.id);
		if (!groups.has(s)) groups.set(s, []);
		groups.get(s).push({
			key: `${node.id}-${i}`,
			label: String(node.label || node.id),
			kind: kindOf(node),
			type: node.type,
			branches: branchesOf(node, edges, labelOf),
		});
	});
	return [...groups.keys()]
		.sort((a, b) => a - b)
		.map((s, i) => ({ number: i + 1, steps: groups.get(s) }));
}
