<template>
	<div class="stat-grid">
		<div class="stat-card">
			<div class="stat-label">Runs</div>
			<div class="stat-value">{{ stats.runs }}</div>
			<div class="stat-sub">in this window</div>
		</div>

		<div class="stat-card">
			<div class="stat-label">Success rate</div>
			<div class="stat-value">{{ formatPercent(stats.success_rate) }}</div>
			<div class="stat-sub">completed without error</div>
		</div>

		<div class="stat-card">
			<div class="stat-label">Avg latency</div>
			<div class="stat-value">{{ formatLatency(stats.avg_latency_seconds) }}</div>
			<div class="stat-sub">per completed run</div>
		</div>

		<div class="stat-card">
			<div class="stat-label">Avg credits</div>
			<div class="stat-value">{{ formatCredits(stats.avg_credits_used) }}</div>
			<div class="stat-sub">per completed run</div>
		</div>

		<div class="stat-card stat-card-trigger">
			<div class="stat-label">Triggered by</div>
			<div class="trigger-list">
				<div v-for="entry in nonZeroTriggers" :key="entry.key" class="trigger-row">
					<span class="trigger-name">{{ entry.label }}</span>
					<span class="trigger-count">{{ entry.count }}</span>
				</div>
				<div v-if="nonZeroTriggers.length === 0" class="trigger-empty">—</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	stats: {
		type: Object,
		required: true,
	},
});

const TRIGGER_LABELS = {
	manual: "Manual",
	scheduled: "Scheduled",
	api: "API",
	doc_event: "Doc event",
};

const nonZeroTriggers = computed(() => {
	const breakdown = props.stats?.trigger_breakdown || {};
	return Object.entries(breakdown)
		.filter(([, count]) => count > 0)
		.map(([key, count]) => ({ key, label: TRIGGER_LABELS[key] || key, count }));
});

function formatPercent(value) {
	if (!Number.isFinite(value)) return "—";
	return `${Math.round(value * 100)}%`;
}

function formatLatency(seconds) {
	if (!seconds) return "—";
	if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
	if (seconds < 60) return `${seconds.toFixed(1)} s`;
	const mins = Math.floor(seconds / 60);
	const rem = Math.round(seconds % 60);
	return `${mins}m ${rem}s`;
}

function formatCredits(value) {
	if (!Number.isFinite(value) || value === 0) return "—";
	if (value < 0.01) return value.toFixed(4);
	if (value < 1) return value.toFixed(3);
	return value.toFixed(2);
}
</script>

<style scoped>
.stat-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
	gap: 0.75rem;
}

.stat-card {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.75rem 0.875rem;
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
	min-height: 92px;
}

.stat-label {
	font-size: 0.6875rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
}

.stat-value {
	font-size: 1.5rem;
	font-weight: 600;
	color: var(--ql-text);
	line-height: 1.1;
}

.stat-sub {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}

/* Trigger card lays its rows vertically — different shape from a single number. */
.stat-card-trigger .trigger-list {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	margin-top: 0.125rem;
}

.trigger-row {
	display: flex;
	justify-content: space-between;
	font-size: 0.8125rem;
	color: var(--ql-text);
}

.trigger-count {
	font-variant-numeric: tabular-nums;
	color: var(--ql-text-muted);
}

.trigger-empty {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}
</style>
