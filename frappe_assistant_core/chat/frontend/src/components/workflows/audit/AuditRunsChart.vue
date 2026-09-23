<template>
	<div class="chart-wrap">
		<div v-if="totalRuns === 0" class="chart-empty">
			<p>No runs in this window.</p>
			<p class="empty-hint">Try a longer time window or run the agent manually.</p>
		</div>

		<template v-else>
			<div class="chart-bars" :style="{ '--bar-count': series.length }">
				<div
					v-for="entry in series"
					:key="entry.date"
					class="chart-col"
					:title="tooltipFor(entry)"
				>
					<div class="chart-stack">
						<div
							v-if="entry.completed"
							class="bar bar-completed"
							:style="{ height: pct(entry.completed) }"
						></div>
						<div
							v-if="entry.failed"
							class="bar bar-failed"
							:style="{ height: pct(entry.failed) }"
						></div>
						<div
							v-if="entry.running"
							class="bar bar-running"
							:style="{ height: pct(entry.running) }"
						></div>
					</div>
					<div class="chart-label">{{ shortDate(entry.date) }}</div>
				</div>
			</div>

			<div class="chart-legend">
				<span class="legend-item"
					><span class="legend-dot dot-completed"></span> Completed</span
				>
				<span class="legend-item"><span class="legend-dot dot-failed"></span> Failed</span>
				<span class="legend-item"
					><span class="legend-dot dot-running"></span> Running</span
				>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	series: {
		type: Array,
		required: true,
	},
});

const totalRuns = computed(() =>
	props.series.reduce(
		(sum, e) => sum + (e.completed || 0) + (e.failed || 0) + (e.running || 0),
		0
	)
);

// Scale all bars relative to the busiest day so the chart fills the
// available height regardless of absolute volume.
const maxRunsInDay = computed(() => {
	let max = 0;
	for (const e of props.series) {
		const total = (e.completed || 0) + (e.failed || 0) + (e.running || 0);
		if (total > max) max = total;
	}
	return max || 1;
});

function pct(value) {
	return `${(value / maxRunsInDay.value) * 100}%`;
}

function shortDate(iso) {
	// "2026-04-30" → "Apr 30". Locale-friendly without dragging in Intl.
	const d = new Date(`${iso}T00:00:00`);
	const months = [
		"Jan",
		"Feb",
		"Mar",
		"Apr",
		"May",
		"Jun",
		"Jul",
		"Aug",
		"Sep",
		"Oct",
		"Nov",
		"Dec",
	];
	return `${months[d.getMonth()]} ${d.getDate()}`;
}

function tooltipFor(entry) {
	const parts = [`${shortDate(entry.date)} ·`];
	if (entry.completed) parts.push(`${entry.completed} completed`);
	if (entry.failed) parts.push(`${entry.failed} failed`);
	if (entry.running) parts.push(`${entry.running} running`);
	if (parts.length === 1) parts.push("no runs");
	return parts.join(" ");
}
</script>

<style scoped>
.chart-wrap {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 1rem;
}

.chart-empty {
	text-align: center;
	padding: 2rem 1rem;
	color: var(--ql-text-muted);
}

.chart-empty p {
	margin: 0 0 0.25rem;
	font-size: 0.875rem;
}

.empty-hint {
	font-size: 0.75rem;
}

.chart-bars {
	display: grid;
	grid-template-columns: repeat(var(--bar-count), 1fr);
	gap: 0.375rem;
	height: 160px;
}

.chart-col {
	display: flex;
	flex-direction: column;
	justify-content: flex-end;
	min-width: 0;
}

.chart-stack {
	display: flex;
	flex-direction: column-reverse;
	flex: 1;
	gap: 1px;
	min-height: 1px;
}

.bar {
	width: 100%;
	border-radius: 2px;
	min-height: 2px;
}

.bar-completed {
	background: var(--ql-success);
}

.bar-failed {
	background: var(--ql-danger);
}

.bar-running {
	background: var(--ql-text-muted);
}

.chart-label {
	margin-top: 0.375rem;
	text-align: center;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.chart-legend {
	display: flex;
	gap: 1rem;
	margin-top: 0.875rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.legend-item {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
}

.legend-dot {
	width: 10px;
	height: 10px;
	border-radius: 2px;
}

.dot-completed {
	background: var(--ql-success);
}

.dot-failed {
	background: var(--ql-danger);
}

.dot-running {
	background: var(--ql-text-muted);
}
</style>
