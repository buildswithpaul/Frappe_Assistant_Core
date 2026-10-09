/**
 * Layered left-to-right layout for graphs that arrive without usable positions
 * (chat-built agents, imported templates). Breadth-first depth from the entry
 * nodes picks the column; order of discovery picks the row.
 */
export const NODE_BOX = { width: 220, height: 90 };
const ORIGIN = 80;
const GAP_X = 300;
const GAP_Y = 140;
// Nodes closer than this on both axes are a pile, not an authored layout.
const STACK_TOLERANCE = 40;

const isPositioned = (n) =>
	n.position && Number.isFinite(n.position.x) && Number.isFinite(n.position.y);

/** True when the graph needs a layout: a node lacks a position or two nodes are stacked. */
export function hasOverlaps(nodes, tolerance = STACK_TOLERANCE) {
	if (nodes.length > 1 && nodes.some((n) => !isPositioned(n))) return true;
	for (let i = 0; i < nodes.length; i++) {
		for (let j = i + 1; j < nodes.length; j++) {
			const a = nodes[i].position;
			const b = nodes[j].position;
			if (Math.abs(a.x - b.x) < tolerance && Math.abs(a.y - b.y) < tolerance) return true;
		}
	}
	return false;
}

export function autoLayout(nodes, edges) {
	const ids = nodes.map((n) => n.id);
	const known = new Set(ids);
	const indegree = new Map(ids.map((id) => [id, 0]));
	const out = new Map(ids.map((id) => [id, []]));
	for (const e of edges) {
		if (!known.has(e.source) || !known.has(e.target) || e.source === e.target) continue;
		out.get(e.source).push(e.target);
		indegree.set(e.target, indegree.get(e.target) + 1);
	}

	const roots = ids.filter((id) => indegree.get(id) === 0 && out.get(id).length > 0);
	const starts = roots.length ? roots : ids.slice(0, 1);
	const layer = new Map();
	const queue = starts.map((id) => [id, 0]);
	while (queue.length) {
		const [id, depth] = queue.shift();
		if (layer.has(id)) continue;
		layer.set(id, depth);
		for (const next of out.get(id)) if (!layer.has(next)) queue.push([next, depth + 1]);
	}

	const extra = layer.size ? Math.max(...layer.values()) + 1 : 0;
	for (const id of ids) if (!layer.has(id)) layer.set(id, extra);

	const rows = new Map();
	return nodes.map((n) => {
		const column = layer.get(n.id);
		const row = rows.get(column) || 0;
		rows.set(column, row + 1);
		return { ...n, position: { x: ORIGIN + column * GAP_X, y: ORIGIN + row * GAP_Y } };
	});
}
