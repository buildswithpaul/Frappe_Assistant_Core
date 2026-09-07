<template>
	<div class="metric-block">
		<div class="metric-title">{{ title }}</div>
		<div class="metric-value-row">
			<span class="metric-value">{{ value }}</span>
			<span v-if="change" class="metric-change" :class="trendClass">
				<svg
					v-if="trend === 'up'"
					class="trend-icon"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M5 10l7-7m0 0l7 7m-7-7v18"
					/>
				</svg>
				<svg
					v-else-if="trend === 'down'"
					class="trend-icon"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M19 14l-7 7m0 0l-7-7m7 7V3"
					/>
				</svg>
				{{ change }}
			</span>
		</div>
		<div v-if="description" class="metric-description">{{ description }}</div>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	title: { type: String, default: "" },
	value: { type: String, default: "" },
	change: { type: String, default: "" },
	trend: { type: String, default: "" },
	description: { type: String, default: "" },
});

const trendClass = computed(() => {
	if (props.trend === "up") return "trend-up";
	if (props.trend === "down") return "trend-down";
	return "trend-flat";
});
</script>

<style scoped>
.metric-block {
	display: inline-flex;
	flex-direction: column;
	padding: 1rem 1.25rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	margin: 0.5rem 0.5rem 0.5rem 0;
	min-width: 140px;
}

.metric-title {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.025em;
	margin-bottom: 0.25rem;
}

.metric-value-row {
	display: flex;
	align-items: baseline;
	gap: 0.5rem;
}

.metric-value {
	font-size: 1.5rem;
	font-weight: 700;
	color: var(--ql-text);
	line-height: 1.2;
	font-variant-numeric: tabular-nums;
}

.metric-change {
	display: inline-flex;
	align-items: center;
	gap: 0.125rem;
	font-size: 0.75rem;
	font-weight: 600;
	padding: 0.125rem 0.375rem;
	border-radius: 0.25rem;
}

.trend-icon {
	width: 0.75rem;
	height: 0.75rem;
}

.trend-up {
	color: #16a34a;
	background: rgba(34, 197, 94, 0.1);
}

.trend-down {
	color: #dc2626;
	background: rgba(239, 68, 68, 0.1);
}

.trend-flat {
	color: #6b7280;
	background: rgba(107, 114, 128, 0.1);
}

.metric-description {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.375rem;
}
</style>
