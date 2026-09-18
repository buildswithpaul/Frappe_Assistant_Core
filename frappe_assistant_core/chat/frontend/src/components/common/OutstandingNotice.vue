<template>
	<div v-if="amount > 0" class="due-notice" :class="`is-${variant}`">
		<div class="due-icon">
			<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
		</div>
		<div class="due-text">
			<strong>{{ formatCurrency(amount, currency) }} outstanding</strong>
			<span>{{ reason }}</span>
		</div>
		<button v-if="showAction" class="due-btn" @click="$emit('pay')">
			{{ actionLabel }}
		</button>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { formatCurrency } from "@/composables/useFormatters";

const props = defineProps({
	// The resolver's shape: { amount, currency, invoice } or null.
	outstanding: { type: Object, default: null },
	variant: { type: String, default: "banner" }, // banner | inline
	showAction: { type: Boolean, default: true },
	actionLabel: { type: String, default: "Pay now" },
	// Why this matters *here* — the consequence differs per surface, and a
	// notice that reads the same in four places gets tuned out in all four.
	reason: {
		type: String,
		default: "Your last renewal payment hasn't gone through yet.",
	},
});

defineEmits(["pay"]);

const amount = computed(() => props.outstanding?.amount || 0);
const currency = computed(() => props.outstanding?.currency || undefined);
</script>

<style scoped>
.due-notice {
	display: flex;
	align-items: center;
	gap: 0.875rem;
	padding: 0.875rem 1rem;
	background: linear-gradient(
		135deg,
		rgba(220, 38, 38, 0.08) 0%,
		rgba(220, 38, 38, 0.04) 100%
	);
	border: 1px solid rgba(220, 38, 38, 0.25);
	border-radius: 0.75rem;
}

.due-notice.is-inline {
	padding: 0.625rem 0.75rem;
	gap: 0.625rem;
}

.due-icon {
	flex-shrink: 0;
	width: 2rem;
	height: 2rem;
	display: flex;
	align-items: center;
	justify-content: center;
	background: rgba(220, 38, 38, 0.15);
	border-radius: 0.5rem;
	color: #dc2626;
}

.due-notice.is-inline .due-icon {
	width: 1.5rem;
	height: 1.5rem;
	border-radius: 0.375rem;
}

.due-icon svg {
	width: 1.125rem;
	height: 1.125rem;
}

.due-notice.is-inline .due-icon svg {
	width: 0.875rem;
	height: 0.875rem;
}

.due-text {
	flex: 1;
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	font-size: 0.8125rem;
	min-width: 0;
}

.due-notice.is-inline .due-text {
	font-size: 0.75rem;
}

.due-text strong {
	color: var(--ql-text);
	font-weight: 600;
}

.due-text span {
	color: var(--ql-text-muted);
}

.due-btn {
	flex-shrink: 0;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 600;
	color: white;
	background: #dc2626;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: background 0.15s ease;
}

.due-notice.is-inline .due-btn {
	padding: 0.375rem 0.75rem;
	font-size: 0.75rem;
}

.due-btn:hover {
	background: #b91c1c;
}

@media (max-width: 640px) {
	.due-notice {
		flex-wrap: wrap;
	}

	.due-btn {
		width: 100%;
	}
}
</style>
