<template>
	<div v-if="graph" class="detail-section">
		<h3 class="section-label">{{ __("How it runs") }}</h3>
		<p v-if="graph.note" class="mini-graph-note">{{ graph.note }}</p>
		<svg
			v-else
			class="mini-graph"
			role="img"
			:aria-label="graph.ariaLabel"
			:viewBox="graph.viewBox"
			preserveAspectRatio="xMidYMid meet"
		>
			<path v-for="(e, i) in graph.edges" :key="`${e.id}-${i}`" class="mini-edge" :d="e.d" />
			<g v-for="(n, i) in graph.nodes" :key="`${n.id}-${i}`">
				<rect
					class="mini-node"
					:x="n.x"
					:y="n.y"
					:width="W"
					:height="H"
					rx="6"
					:style="{ stroke: n.color }"
				/>
				<text class="mini-label" :x="n.x + 10" :y="n.y + H / 2 + 4">{{ n.short }}</text>
			</g>
		</svg>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";
import { graphJsonToVueFlow, NODE_TYPES } from "../graphUtils";
import { autoLayout } from "../graphLayout";

const props = defineProps({ graphJson: { type: [String, Object], default: null } });

const W = 180;
const H = 40;
const PAD = 20;
const MAX_LABEL = 22;
const MAX_NODES = 60;
const MAX_ARIA_LABELS = 12;
const colorOf = (type) => NODE_TYPES.find((t) => t.type === type)?.color || "var(--ql-border)";

function shorten(text) {
	return text.length > MAX_LABEL ? `${text.slice(0, MAX_LABEL - 1)}…` : text;
}

function curve(a, b) {
	const x1 = a.x + W;
	const y1 = a.y + H / 2;
	const x2 = b.x;
	const y2 = b.y + H / 2;
	const mid = (x1 + x2) / 2;
	return `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`;
}

function build(parsed) {
	const placed = autoLayout(parsed.nodes, parsed.edges);
	const byId = new Map(placed.map((n) => [n.id, n.position]));
	const xs = placed.map((n) => n.position.x);
	const ys = placed.map((n) => n.position.y);
	const minX = Math.min(...xs) - PAD;
	const minY = Math.min(...ys) - PAD;
	const width = Math.max(...xs) + W + PAD - minX;
	const height = Math.max(...ys) + H + PAD - minY;
	return {
		ariaLabel: __("Agent graph: {0}", [
			placed
				.slice(0, MAX_ARIA_LABELS)
				.map((n) => String(n.data?.label || n.id))
				.join(" → "),
		]),
		viewBox: `${minX} ${minY} ${width} ${height}`,
		nodes: placed.map((n) => {
			const label = String(n.data?.label || n.id);
			return {
				id: n.id,
				x: n.position.x,
				y: n.position.y,
				label,
				short: shorten(label),
				color: colorOf(n.type),
			};
		}),
		edges: parsed.edges
			.filter((e) => byId.has(e.source) && byId.has(e.target))
			.map((e) => ({ id: e.id, d: curve(byId.get(e.source), byId.get(e.target)) })),
	};
}

const graph = computed(() => {
	if (!props.graphJson) return null;
	try {
		const parsed = graphJsonToVueFlow(props.graphJson);
		if (!parsed.nodes.length) return null;
		if (parsed.nodes.length > MAX_NODES) {
			return {
				note: __("{0} steps — open the template to see the full graph", [parsed.nodes.length]),
			};
		}
		return build(parsed);
	} catch {
		return { note: __("This template's steps can't be previewed.") };
	}
});
</script>

<style scoped>
.detail-section {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}
.mini-graph {
	width: 100%;
	max-height: 14rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
}
.mini-node {
	fill: var(--ql-surface);
	stroke-width: 1.5;
}
.mini-edge {
	fill: none;
	stroke: var(--ql-edge);
	stroke-width: 1.5;
}
.mini-label {
	font-size: 12px;
	fill: var(--ql-text);
}
.mini-graph-note {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin: 0;
}
.section-label {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	margin: 0;
}
</style>
