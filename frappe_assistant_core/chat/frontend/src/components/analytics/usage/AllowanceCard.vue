<template>
	<div class="allowance-card">
		<div class="card-label">{{ label || __("This month") }}</div>
		<template v-if="unlimited">
			<div class="card-value">{{ __("Unlimited plan") }}</div>
		</template>
		<template v-else>
			<div class="card-value">
				{{ formatNumber(used) }}
				<span class="card-total">/ {{ formatNumber(total) }}</span>
			</div>
			<div class="allowance-bar" :class="toneClass" aria-hidden="true">
				<div class="allowance-fill" :style="{ width: `${percent}%` }"></div>
			</div>
			<div class="card-foot">
				<span class="card-sub">{{ percent }}%</span>
				<span v-if="resetDate" class="card-sub">{{ __("Resets on {0}", [resetDate]) }}</span>
			</div>
		</template>
		<div v-if="note" class="card-sub card-note">{{ note }}</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";

const props = defineProps({
	used: { type: Number, default: 0 },
	total: { type: Number, default: 0 },
	percent: { type: Number, default: 0 },
	unlimited: { type: Boolean, default: false },
	resetDate: { type: String, default: null },
	label: { type: String, default: "" },
	note: { type: String, default: "" },
});

// Same thresholds as the chat CreditMeter so both surfaces warn at the same points.
const toneClass = computed(() => {
	if (props.percent >= 100) return "is-exhausted";
	if (props.percent >= 90) return "is-critical";
	if (props.percent >= 80) return "is-warning";
	return "";
});

function formatNumber(val) {
	return Number(val || 0).toLocaleString("en-US");
}
</script>

<style scoped>
.allowance-card {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	padding: 1.25rem;
}

.card-label {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
	margin-bottom: 0.5rem;
}

.card-value {
	font-size: 1.75rem;
	font-weight: 700;
	color: var(--ql-text);
	line-height: 1.2;
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.card-total {
	font-size: 1rem;
	font-weight: 500;
	color: var(--ql-text-muted);
}

.allowance-bar {
	height: 6px;
	border-radius: 999px;
	background: var(--ql-border);
	overflow: hidden;
	margin-top: 0.75rem;
}

.allowance-fill {
	height: 100%;
	border-radius: 999px;
	background: var(--ql-accent);
	transition: width 0.4s ease;
}

.is-warning .allowance-fill {
	background: #f59e0b;
}

.is-critical .allowance-fill,
.is-exhausted .allowance-fill {
	background: #dc2626;
}

.card-foot {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
	margin-top: 0.5rem;
}

.card-sub {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.card-note {
	margin-top: 0.5rem;
}
</style>
