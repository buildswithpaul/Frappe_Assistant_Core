<template>
	<div class="sources-block">
		<button class="sources-header" :class="{ expanded }" @click="expanded = !expanded">
			<svg
				class="sources-chevron"
				:class="{ rotated: expanded }"
				viewBox="0 0 20 20"
				fill="currentColor"
				aria-hidden="true"
			>
				<path
					fill-rule="evenodd"
					d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.24 4.5a.75.75 0 01-1.08 0l-4.24-4.5a.75.75 0 01.02-1.06z"
					clip-rule="evenodd"
				/>
			</svg>
			<span class="sources-label">Sources</span>
			<span class="sources-count">{{ items.length }}</span>
		</button>

		<ul v-show="expanded" class="sources-list">
			<li
				v-for="item in items"
				:id="`source-${item.n}`"
				:key="`${item.document_id}-${item.n}`"
				ref="sourceItems"
				class="source-item"
			>
				<span class="source-marker">[{{ item.n }}]</span>
				<span class="source-name" :title="item.document_name">
					{{ item.document_name || "Unknown document" }}
				</span>
				<span v-if="item.document_type" class="source-type">
					{{ item.document_type }}
				</span>
				<span v-if="passageCount(item) > 1" class="source-passages">
					{{ passageCount(item) }} sections cited
				</span>
				<span
					class="source-relevance"
					:class="relevanceLabel(item.score).className"
					:title="`Similarity score: ${formatScore(item.score)}`"
				>
					<span class="source-relevance-dot" aria-hidden="true">•</span>
					{{ relevanceLabel(item.score).label }}
				</span>
				<button
					class="source-open"
					:title="`Open ${item.document_name || 'document'}`"
					@click.stop="$emit('preview-document', item)"
				>
					<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
						<path
							d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z"
						/>
						<path
							d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z"
						/>
					</svg>
					<span>Open</span>
				</button>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { ref } from "vue";

defineProps({
	items: {
		type: Array,
		required: true,
	},
});

defineEmits(["preview-document"]);

const expanded = ref(false);
const sourceItems = ref([]);

function formatScore(score) {
	if (typeof score !== "number") return "";
	return score.toFixed(2);
}

// After B4 dedupe: one source entry covers N chunks from the same document.
// Older snapshots may still carry a single `chunk_id` (pre-B4 schema), so
// fall back to 1 in that case. Used to show "N sections cited" next to sources
// that came from multiple chunks of the same document.
function passageCount(item) {
	if (Array.isArray(item.chunk_ids)) return item.chunk_ids.length;
	if (item.chunk_id) return 1;
	return 1;
}

// Map similarity (0–1) to a user-friendly label. Thresholds chosen against
// the default rag_min_score of 0.5 and observed real-world distribution:
// production queries typically land in the 0.30–0.50 range for loose matches
// and 0.65+ for strong topical alignment. Raw decimal stays in the tooltip.
function relevanceLabel(score) {
	if (typeof score !== "number") return { label: "", className: "" };
	if (score >= 0.65) return { label: "High", className: "rel-high" };
	if (score >= 0.4) return { label: "Medium", className: "rel-med" };
	return { label: "Low", className: "rel-low" };
}

// Exposed so CitationPill (via MessageBlockRenderer) can briefly highlight
// the matching source card when the user clicks an inline [N] pill.
function flashItem(n) {
	const el = document.getElementById(`source-${n}`);
	if (!el) return;
	if (!expanded.value) expanded.value = true;
	// Wait for the list to expand before scrolling
	requestAnimationFrame(() => {
		el.scrollIntoView({ behavior: "smooth", block: "center" });
		el.classList.remove("highlight");
		// Force reflow so the animation restarts if the user clicks again
		void el.offsetWidth;
		el.classList.add("highlight");
		setTimeout(() => el.classList.remove("highlight"), 1500);
	});
}

defineExpose({ flashItem });
</script>

<style scoped>
.sources-block {
	margin-top: 0.75rem;
	padding: 0.5rem 0.75rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	background-color: var(--ql-subtle);
}

.sources-header {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	width: 100%;
	padding: 0;
	background: transparent;
	border: none;
	cursor: pointer;
	color: var(--ql-text-muted);
	font-size: 0.8125rem;
	font-weight: 500;
	text-align: left;
}

.sources-header:hover {
	color: var(--ql-text);
}

.sources-chevron {
	width: 0.875rem;
	height: 0.875rem;
	transition: transform 150ms ease;
	flex-shrink: 0;
}

.sources-chevron.rotated {
	transform: rotate(-180deg);
}

.sources-label {
	letter-spacing: 0.01em;
}

.sources-count {
	padding: 0.0625rem 0.375rem;
	background-color: var(--ql-subtle);
	border-radius: 999px;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
}

.sources-list {
	list-style: none;
	margin: 0.5rem 0 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}

.source-item {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.375rem 0.5rem;
	border-radius: 0.375rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	transition: background-color 120ms ease;
}

.source-item:hover {
	background-color: var(--ql-subtle);
}

.source-item.highlight {
	animation: source-flash 1.5s ease-out;
}

@keyframes source-flash {
	0% {
		background-color: var(--ql-accent-soft);
	}
	100% {
		background-color: transparent;
	}
}

.source-marker {
	font-variant-numeric: tabular-nums;
	font-weight: 600;
	color: var(--ql-accent);
	min-width: 1.5rem;
}

.source-name {
	flex: 1;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.source-type {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	font-weight: 400;
}

.source-passages {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	font-variant-numeric: tabular-nums;
}

.source-relevance {
	display: inline-flex;
	align-items: center;
	gap: 0.1875rem;
	font-size: 0.75rem;
	font-weight: 500;
	min-width: 3.75rem;
	justify-content: flex-end;
}

.source-relevance-dot {
	line-height: 1;
	font-size: 1rem;
}

.rel-high {
	color: var(--ql-success);
}
.rel-med {
	color: var(--ql-warning);
}
.rel-low {
	color: var(--ql-text-muted);
}

.source-open {
	display: inline-flex;
	align-items: center;
	gap: 0.25rem;
	padding: 0.1875rem 0.5rem;
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.3125rem;
	color: var(--ql-text-muted);
	font-size: 0.75rem;
	font-weight: 500;
	cursor: pointer;
	transition: color 120ms ease, border-color 120ms ease, background-color 120ms ease;
}

.source-open:hover {
	color: var(--ql-accent);
	border-color: var(--ql-accent);
	background-color: var(--ql-subtle);
}

.source-open svg {
	width: 0.8125rem;
	height: 0.8125rem;
	flex-shrink: 0;
}
</style>
