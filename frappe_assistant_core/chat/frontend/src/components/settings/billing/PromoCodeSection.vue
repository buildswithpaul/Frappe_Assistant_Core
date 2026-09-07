<template>
	<div class="promo-section">
		<template v-if="appliedPromo">
			<div class="promo-applied">
				<svg
					class="promo-check-icon"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
				<span class="promo-text">
					<strong>{{ appliedPromo.code }}</strong> &mdash;
					{{ appliedPromo.display || "Applied" }}
					<template v-if="savings">
						<span class="promo-savings">(saves {{ savings }})</span>
					</template>
				</span>
				<button class="promo-remove" @click="$emit('remove-promo')">Remove</button>
			</div>
		</template>
		<template v-else>
			<div v-if="!showPromo" class="promo-link-row">
				<button class="promo-link" @click="showPromo = true">Have a promo code?</button>
			</div>
			<div v-else class="promo-input-row">
				<input
					v-model="promoCode"
					type="text"
					class="promo-input"
					placeholder="PROMO CODE"
					aria-label="Promo code"
					@input="promoCode = promoCode.toUpperCase()"
					@keyup.enter="$emit('validate-promo', promoCode)"
					:disabled="validatingPromo"
				/>
				<button
					class="promo-apply"
					@click="$emit('validate-promo', promoCode)"
					:disabled="validatingPromo || !promoCode.trim()"
				>
					{{ validatingPromo ? "..." : "Apply" }}
				</button>
			</div>
			<p v-if="promoError" class="promo-error" role="alert">{{ promoError }}</p>
		</template>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

import { formatCurrency } from "@/composables/_billing/billingFormatters";

const props = defineProps({
	appliedPromo: {
		type: Object,
		default: null,
	},
	promoError: {
		type: String,
		default: null,
	},
	validatingPromo: {
		type: Boolean,
		default: false,
	},
});

defineEmits(["validate-promo", "remove-promo"]);

const showPromo = ref(false);
const promoCode = ref("");

// The saving is denominated in the tenant's own currency, which AR returns
// alongside the amount. It used to be a hardcoded "$": harmless only while
// discount_amount was never populated, and the moment it was, an Indian
// tenant taking 10% off a ₹2,499 plan was told they saved "$249.90".
const savings = computed(() => {
	const amount = props.appliedPromo?.discount_amount;
	if (!amount) return null;
	return formatCurrency(Number(amount), props.appliedPromo?.currency);
});
</script>

<style scoped>
.promo-section {
	margin-top: 1.25rem;
	padding-top: 1rem;
	border-top: 1px solid var(--ql-border);
}

.promo-link-row {
	text-align: center;
}

.promo-link {
	padding: 0;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-accent);
	background: none;
	border: none;
	cursor: pointer;
	text-decoration: underline;
	text-underline-offset: 2px;
}

.promo-link:hover {
	opacity: 0.8;
}

.promo-input-row {
	display: flex;
	gap: 0.5rem;
}

.promo-input {
	flex: 1;
	padding: 0.5rem 0.75rem;
	font-size: 0.8125rem;
	font-family: monospace;
	letter-spacing: 0.06em;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	outline: none;
	transition: border-color 0.15s ease;
}

.promo-input:focus {
	border-color: var(--ql-accent);
}
.promo-input:disabled {
	opacity: 0.6;
}

.promo-apply {
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	white-space: nowrap;
}

.promo-apply:hover:not(:disabled) {
	opacity: 0.9;
}
.promo-apply:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

.promo-applied {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.75rem;
	background: rgba(34, 197, 94, 0.08);
	border: 1px solid rgba(34, 197, 94, 0.25);
	border-radius: 0.375rem;
}

.promo-check-icon {
	width: 1rem;
	height: 1rem;
	color: #22c55e;
	flex-shrink: 0;
}

.promo-text {
	flex: 1;
	font-size: 0.8125rem;
	color: var(--ql-text);
}

.promo-remove {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	cursor: pointer;
	text-decoration: underline;
}

.promo-remove:hover {
	color: var(--ql-danger, #ef4444);
}

.promo-savings {
	color: #22c55e;
	font-weight: 500;
}

.promo-error {
	margin-top: 0.375rem;
	font-size: 0.75rem;
	color: var(--ql-danger, #ef4444);
}
</style>
