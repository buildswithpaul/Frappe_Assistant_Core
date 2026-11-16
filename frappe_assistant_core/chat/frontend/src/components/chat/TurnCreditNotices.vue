<template>
	<div v-if="message.lowBalance" class="credit-notice low-balance-notice">
		<svg class="credit-notice-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
				d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
		</svg>
		<span>{{ lowBalanceText }}</span>
		<button v-if="isLatest" class="credit-notice-btn send-anyway-btn" @click="$emit('send-anyway', message)">
			{{ __("Send anyway") }}
		</button>
	</div>

	<div v-if="message.budgetReached" class="credit-notice budget-notice">
		<svg class="credit-notice-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
				d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
		</svg>
		<span>{{ budgetText }}</span>
		<button v-if="isLatest" class="credit-notice-btn continue-btn" @click="$emit('continue-turn')">
			{{ __("Continue") }}
		</button>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";

const props = defineProps({
	message: { type: Object, required: true },
	isLatest: { type: Boolean, default: false },
});

defineEmits(["send-anyway", "continue-turn"]);

const credits = (value) => Number(value || 0).toFixed(1);

const BUDGET_TEXTS = {
	limit_credits: () => __("This turn reached its credit limit."),
	limit_turns: () => __("This answer reached its step limit."),
	limit_total_tokens: () => __("This answer reached its length limit."),
	limit_output_tokens: () => __("This answer reached its length limit."),
};

const budgetText = computed(() =>
	(BUDGET_TEXTS[props.message.budgetStopReason] || (() => __("This answer was stopped at a limit.")))()
);

const lowBalanceText = computed(() =>
	__("This message may cost about {0} credits and you have {1} left.", [
		credits(props.message.lowBalance.estimate),
		credits(props.message.lowBalance.balance),
	])
);
</script>

<style scoped>
.credit-notice {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	margin-top: 0.75rem;
	padding: 0.5rem 0.75rem;
	background-color: var(--ql-gold-soft);
	border: 1px solid var(--ql-gold-soft);
	border-radius: 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
	line-height: 1.4;
}

.credit-notice-icon {
	flex-shrink: 0;
	width: 1rem;
	height: 1rem;
	color: var(--ql-warning);
}

.credit-notice-btn {
	margin-left: auto;
	flex-shrink: 0;
	padding: 0.3rem 0.75rem;
	background-color: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	cursor: pointer;
	transition: all 0.15s ease;
}

.credit-notice-btn:hover {
	background-color: var(--ql-subtle);
	border-color: var(--ql-text-muted);
}
</style>
