<template>
	<span v-if="shouldShow" class="trend-badge" :class="toneClass" :title="tooltip">
		<svg
			v-if="trend.direction === 'up'"
			class="trend-icon"
			viewBox="0 0 12 12"
			aria-hidden="true"
		>
			<path d="M2 9l4-4 4 4" stroke="currentColor" stroke-width="1.5" fill="none" />
		</svg>
		<svg
			v-else-if="trend.direction === 'down'"
			class="trend-icon"
			viewBox="0 0 12 12"
			aria-hidden="true"
		>
			<path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="1.5" fill="none" />
		</svg>
		<svg v-else class="trend-icon" viewBox="0 0 12 12" aria-hidden="true">
			<path d="M2 6h8" stroke="currentColor" stroke-width="1.5" fill="none" />
		</svg>
		<span>{{ label }}</span>
	</span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	trend: { type: Object, required: true },
	// 'cost' = rising is bad (spend/credits). 'neutral' = no value judgment
	// (requests, active users). Default is neutral so color choice is
	// opt-in rather than magic.
	tone: { type: String, default: "neutral" },
});

// Build the final CSS class: base direction + intent modifier. Cost-tone
// "up" (more spend) becomes red; "down" (less spend) becomes green.
const toneClass = computed(() => {
	const dir = props.trend?.direction;
	if (dir === "new") return "trend-new";
	if (dir === "flat") return "trend-flat";
	if (props.tone === "cost") {
		return dir === "up" ? "trend-bad" : "trend-good";
	}
	return dir === "up" ? "trend-good" : "trend-bad";
});

const shouldShow = computed(() => {
	if (!props.trend) return false;
	if (props.trend.direction === "new") return true;
	return props.trend.percent !== null;
});

const label = computed(() => {
	if (props.trend.direction === "new") return "new";
	const p = props.trend.percent;
	if (p === null || p === undefined) return "";
	const sign = p > 0 ? "+" : "";
	return `${sign}${p}%`;
});

const tooltip = computed(() => {
	const t = props.trend;
	if (t.direction === "new") return "First usage in this period";
	return `${Math.round(t.recent).toLocaleString()} recent · ${Math.round(
		t.prior
	).toLocaleString()} earlier in period`;
});
</script>

<style scoped>
.trend-badge {
	display: inline-flex;
	align-items: center;
	gap: 0.2rem;
	padding: 0.1rem 0.4rem;
	font-size: 0.7rem;
	font-weight: 600;
	border-radius: 0.375rem;
	line-height: 1;
	white-space: nowrap;
}

.trend-icon {
	width: 10px;
	height: 10px;
	flex-shrink: 0;
}

.trend-good {
	background: color-mix(in srgb, var(--ql-success) 12%, transparent);
	color: var(--ql-success);
}

.trend-bad {
	background: color-mix(in srgb, var(--ql-danger) 12%, transparent);
	color: var(--ql-danger);
}

.trend-flat {
	background: var(--ql-bg);
	color: var(--ql-text-muted);
}

.trend-new {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}
</style>
