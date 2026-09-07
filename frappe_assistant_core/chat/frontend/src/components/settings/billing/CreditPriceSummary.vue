<template>
	<div class="price-summary">
		<div class="price-row">
			<span class="price-label">{{ creditAmount.toLocaleString() }} credits</span>
			<span class="price-value">{{ formattedPrice }}</span>
		</div>
		<p v-if="localCurrency" class="local-currency-note">
			Payment processed in {{ localCurrency }} at current exchange rate
		</p>
	</div>
</template>

<script setup>
import { computed } from "vue";

// Pack-rate pricing: total = (creditAmount / packCredits) * packPrice
// Configured globally on AR Payment Gateway Settings; flat across all plans.
const props = defineProps({
	creditAmount: {
		type: Number,
		required: true,
	},
	packCredits: {
		type: Number,
		default: 2000,
	},
	packPrice: {
		type: Number,
		default: 5,
	},
	symbol: {
		type: String,
		default: "$",
	},
	localCurrency: {
		type: String,
		default: "",
	},
});

const calculatedPrice = computed(() => {
	const per = props.packCredits || 2000;
	const price = props.packPrice || 0;
	if (per <= 0 || price <= 0) return 0;
	return (props.creditAmount / per) * price;
});

const formattedPrice = computed(() => {
	return `${props.symbol}${calculatedPrice.value.toLocaleString(undefined, {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	})}`;
});
</script>

<style scoped>
.price-summary {
	padding: 1rem;
	background: var(--ql-subtle);
	border-radius: 0.75rem;
	border: 1px solid var(--ql-border);
}

.price-row {
	display: flex;
	justify-content: space-between;
	align-items: center;
}

.price-label {
	font-size: 0.9375rem;
	color: var(--ql-text);
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.price-value {
	font-size: 1.25rem;
	font-weight: 700;
	color: var(--ql-text);
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.local-currency-note {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.5rem;
}
</style>
