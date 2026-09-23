<template>
	<div :class="['gateway-card', { selected }]" @click="$emit('select', gateway.name)">
		<!-- Recommended Badge -->
		<div v-if="gateway.is_recommended" class="recommended-badge">Recommended</div>

		<!-- Gateway Header -->
		<div class="gateway-header">
			<!-- Radio Indicator -->
			<div class="radio-indicator">
				<div class="radio-outer">
					<div v-if="selected" class="radio-inner"></div>
				</div>
			</div>

			<!-- Gateway Name -->
			<div class="gateway-name-section">
				<h3 class="gateway-name">{{ gateway.display_name }}</h3>
				<p class="gateway-subtitle">{{ gateway.description }}</p>
			</div>
		</div>

		<!-- Pricing -->
		<div class="gateway-pricing">
			<span class="price">{{ formattedPrice }}</span>
			<span class="period">/{{ billingCycle === "annual" ? "year" : "month" }}</span>
			<span v-if="billingCycle === 'annual'" class="savings-badge">Save 17%</span>
		</div>
		<p v-if="gateway.local_currency" class="gateway-note">
			Payment processed in {{ gateway.local_currency }} at current exchange rate
		</p>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	gateway: {
		type: Object,
		required: true,
	},
	selected: {
		type: Boolean,
		default: false,
	},
	billingCycle: {
		type: String,
		default: "monthly",
	},
	planId: {
		type: String,
		default: "",
	},
	planName: {
		type: String,
		default: "",
	},
});

defineEmits(["select"]);

function formatPrice(gateway) {
	const plans = gateway.plans || {};
	const planPricing = plans[props.planId] || plans[props.planName] || {};
	const price = props.billingCycle === "annual" ? planPricing.annual : planPricing.monthly;

	if (price === undefined || price === null) {
		return `${gateway.currency_symbol || "$"}--`;
	}

	return `${gateway.currency_symbol || "$"}${price.toLocaleString()}`;
}

const formattedPrice = computed(() => formatPrice(props.gateway));
</script>

<style scoped>
.gateway-card {
	position: relative;
	padding: 1.25rem;
	border: 2px solid var(--ql-border);
	border-radius: 0.75rem;
	cursor: pointer;
	transition: all 0.15s ease;
	background: var(--ql-surface);
}

.gateway-card:hover {
	border-color: var(--ql-accent);
	background: var(--ql-subtle);
}

.gateway-card.selected {
	border-color: var(--ql-accent);
	background: var(--ql-subtle);
	box-shadow: 0 0 0 3px rgba(15, 110, 92, 0.15);
}

.recommended-badge {
	position: absolute;
	top: -0.625rem;
	right: 1rem;
	padding: 0.25rem 0.625rem;
	font-size: 0.6875rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.025em;
	color: white;
	background-color: #22c55e;
	border-radius: 0.25rem;
}

.gateway-header {
	display: flex;
	align-items: flex-start;
	gap: 0.875rem;
}

.radio-indicator {
	flex-shrink: 0;
	padding-top: 0.125rem;
}

.radio-outer {
	width: 1.25rem;
	height: 1.25rem;
	border: 2px solid var(--ql-border);
	border-radius: 50%;
	display: flex;
	align-items: center;
	justify-content: center;
	transition: border-color 0.15s ease;
}

.gateway-card.selected .radio-outer {
	border-color: var(--ql-accent);
}

.radio-inner {
	width: 0.625rem;
	height: 0.625rem;
	background-color: var(--ql-accent);
	border-radius: 50%;
}

.gateway-name-section {
	flex: 1;
}

.gateway-name {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 0.25rem 0;
}

.gateway-subtitle {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin: 0;
}

.gateway-pricing {
	display: flex;
	align-items: baseline;
	gap: 0.25rem;
	margin-top: 0.875rem;
	padding-left: 2.125rem;
}

.price {
	font-size: 1.5rem;
	font-weight: 700;
	color: var(--ql-text);
}

.period {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}

.savings-badge {
	margin-left: 0.5rem;
	padding: 0.125rem 0.5rem;
	font-size: 0.6875rem;
	font-weight: 600;
	color: #22c55e;
	background-color: rgba(34, 197, 94, 0.1);
	border-radius: 0.25rem;
}

.gateway-note {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.375rem;
	padding-left: 2.125rem;
}

/* Mobile Adjustments */
@media (max-width: 480px) {
	.gateway-card {
		padding: 1rem;
	}

	.gateway-pricing {
		padding-left: 0;
		margin-top: 1rem;
	}

	.price {
		font-size: 1.25rem;
	}
}
</style>
