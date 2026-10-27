<template>
	<div class="extra-card">
		<div class="card-label">{{ __("Extra credits") }}</div>
		<div class="card-value">{{ Number(balance || 0).toLocaleString("en-US") }}</div>
		<div class="card-sub">{{ __("Used automatically once the monthly allowance runs out. They carry over.") }}</div>
		<button type="button" class="buy-btn" data-test="buy-credits" @click="emit('buy-credits')">
			{{ __("Buy credits") }}
		</button>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({
	balance: { type: Number, default: 0 },
});

const emit = defineEmits(["buy-credits"]);
</script>

<style scoped>
.extra-card {
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

.card-sub {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.25rem;
}

.buy-btn {
	margin-top: 0.75rem;
	padding: 0.375rem 0.75rem;
	border-radius: 0.5rem;
	border: 1px solid var(--ql-border);
	background: var(--ql-surface);
	color: var(--ql-text);
	font-size: 0.8125rem;
	font-weight: 500;
	cursor: pointer;
}

.buy-btn:hover {
	border-color: var(--ql-accent);
	color: var(--ql-accent);
}
</style>
