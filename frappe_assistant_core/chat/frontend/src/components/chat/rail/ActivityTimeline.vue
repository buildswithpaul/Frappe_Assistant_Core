<template>
	<section v-if="rows.length" class="tl-section">
		<div class="tl-head">Now · this turn</div>
		<button v-if="compressed" class="tl-summary" @click="compressed = false">
			{{ rows.length }} action{{ rows.length === 1 ? "" : "s" }}<template v-if="totalLabel"> · {{ totalLabel }}</template>
		</button>
		<ul v-else class="tl-list">
			<li v-for="row in rows" :key="row.id" class="tl-row" :class="`is-${row.status}`">
				<span class="tl-node" aria-hidden="true">
					<template v-if="row.status === 'success'">✓</template>
					<template v-else-if="row.status === 'error'">✗</template>
					<template v-else-if="row.status === 'cancelled'">⊘</template>
				</span>
				<span class="tl-label">{{ row.label }}</span>
				<span class="tl-duration">{{ durationLabel(row) }}</span>
			</li>
		</ul>
	</section>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from "vue";
import { toolDurationMs } from "@/composables/useActivityTimeline.js";

const props = defineProps({ rows: { type: Array, default: () => [] } });

const compressed = ref(false);
const now = ref(Date.now());
let ticker = null;
let compressTimer = null;

const anyRunning = computed(() => props.rows.some((r) => r.status === "running"));

function fmt(ms) {
	if (ms == null) return "";
	if (ms < 1000) return `${ms}ms`;
	if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
	return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

function durationLabel(row) {
	const done = toolDurationMs(row.block);
	if (done != null) return fmt(done);
	if (row.status === "running" && row.block?.startTime) {
		const live = now.value - new Date(row.block.startTime).getTime();
		return Number.isFinite(live) && live > 0 ? `${fmt(live)}…` : "";
	}
	return "";
}

const totalLabel = computed(() => {
	const starts = props.rows.map((r) => r.block?.startTime && new Date(r.block.startTime).getTime()).filter(Number.isFinite);
	const ends = props.rows.map((r) => r.block?.endTime && new Date(r.block.endTime).getTime()).filter(Number.isFinite);
	if (!starts.length || !ends.length) return "";
	return fmt(Math.max(...ends) - Math.min(...starts));
});

watch(anyRunning, (running, wasRunning) => {
	if (running) {
		compressed.value = false;
		if (compressTimer) clearTimeout(compressTimer);
		if (!ticker) ticker = setInterval(() => { now.value = Date.now(); }, 1000);
	} else {
		if (ticker) { clearInterval(ticker); ticker = null; }
		if (wasRunning) compressTimer = setTimeout(() => { compressed.value = true; }, 2500);
	}
}, { immediate: true });

onUnmounted(() => {
	if (ticker) clearInterval(ticker);
	if (compressTimer) clearTimeout(compressTimer);
});
</script>

<style scoped>
.tl-section {
	display: flex;
	flex-direction: column;
	gap: 6px;
}
.tl-head {
	font-size: 10px;
	text-transform: uppercase;
	letter-spacing: 0.08em;
	color: var(--ql-text-muted);
}
.tl-list {
	position: relative;
	display: flex;
	flex-direction: column;
	gap: 0;
	margin: 0;
	padding: 0;
	list-style: none;
}
.tl-list::before {
	content: "";
	position: absolute;
	top: 2px;
	bottom: 2px;
	left: 7px;
	width: 2px;
	background: var(--ql-border);
}
.tl-row {
	position: relative;
	display: flex;
	gap: 9px;
	align-items: baseline;
	font-size: 11.5px;
	line-height: 1.5;
	padding: 3px 0;
}
.tl-node {
	position: relative;
	flex-shrink: 0;
	width: 15px;
	height: 15px;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 9px;
	line-height: 1;
	background: var(--ql-surface);
}
.tl-row.is-success .tl-node {
	border: 1.5px solid var(--ql-accent);
	border-radius: 50%;
	color: var(--ql-accent);
}
.tl-row.is-error .tl-node {
	border: 1.5px solid var(--ql-danger);
	border-radius: 50%;
	color: var(--ql-danger);
}
.tl-row.is-cancelled .tl-node {
	border: 1.5px solid var(--ql-text-muted);
	border-radius: 50%;
	color: var(--ql-text-muted);
}
.tl-row.is-running .tl-node::after {
	content: "";
	width: 7px;
	height: 7px;
	border-radius: 50%;
	background: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
	animation: tl-pulse 1.4s ease-in-out infinite;
}
.tl-label {
	flex: 1;
	color: var(--ql-text);
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.tl-duration {
	flex-shrink: 0;
	font-family: var(--ql-font-mono);
	font-variant-numeric: tabular-nums;
	font-size: 10.5px;
	color: var(--ql-text-muted);
}
.tl-summary {
	display: block;
	width: 100%;
	text-align: left;
	border: none;
	border-radius: 7px;
	background: transparent;
	padding: 4px 6px;
	margin: 0 -6px;
	font-size: 11.5px;
	color: var(--ql-text-muted);
	cursor: pointer;
}
.tl-summary:hover {
	background: var(--ql-subtle);
}

@keyframes tl-pulse {
	0%, 100% {
		opacity: 1;
	}
	50% {
		opacity: 0.4;
	}
}
@media (prefers-reduced-motion: reduce) {
	.tl-row.is-running .tl-node::after {
		animation: none;
	}
}
</style>
