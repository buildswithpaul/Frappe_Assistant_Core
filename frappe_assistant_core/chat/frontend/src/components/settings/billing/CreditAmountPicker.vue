<template>
	<div class="credit-amount-picker">
		<!-- Credit Amount Input -->
		<div class="form-group">
			<label for="credit-amount">Credit Amount</label>
			<div class="credit-input-wrap">
				<input
					id="credit-amount"
					:value="creditAmount"
					@input="handleInput"
					type="number"
					:min="minimumPurchase"
					:step="10000"
					class="form-input credit-input"
				/>
				<span class="credit-suffix">credits</span>
			</div>
			<p v-if="creditAmount < minimumPurchase" class="field-error">
				Minimum purchase is {{ minimumPurchase.toLocaleString() }} credits
			</p>
		</div>

		<!-- Quick Select Buttons -->
		<div class="quick-select">
			<button
				v-for="preset in presets"
				:key="preset"
				:class="['preset-btn', { active: creditAmount === preset }]"
				@click="$emit('update:creditAmount', preset)"
			>
				{{ formatCompact(preset) }}
			</button>
		</div>

		<!-- Gateway Selection -->
		<div v-if="gateways.length > 1" class="form-group">
			<label>Payment Method</label>
			<div class="gateway-grid">
				<div
					v-for="gw in gateways"
					:key="gw.name"
					:class="['gateway-card', { selected: selectedGateway === gw.name }]"
					@click="$emit('update:selectedGateway', gw.name)"
				>
					<div class="radio-outer">
						<div v-if="selectedGateway === gw.name" class="radio-inner"></div>
					</div>
					<div class="gateway-info">
						<span class="gateway-name">{{ gw.display_name }}</span>
						<span class="gateway-currency">{{ gw.currency_symbol || "$" }}</span>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
defineProps({
	creditAmount: {
		type: Number,
		required: true,
	},
	gateways: {
		type: Array,
		default: () => [],
	},
	selectedGateway: {
		type: String,
		default: null,
	},
	minimumPurchase: {
		type: Number,
		default: 10000,
	},
	presets: {
		type: Array,
		default: () => [10000, 50000, 100000, 500000],
	},
});

const emit = defineEmits(["update:creditAmount", "update:selectedGateway"]);

function handleInput(event) {
	let value = Number(event.target.value);
	if (value < 0) value = 0;
	emit("update:creditAmount", value);
}

function formatCompact(num) {
	if (num >= 1000000) return `${num / 1000000}M`;
	if (num >= 1000) return `${num / 1000}K`;
	return num.toString();
}
</script>

<style scoped>
.credit-amount-picker {
	display: flex;
	flex-direction: column;
	gap: 1.25rem;
}

.form-group {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.form-group label {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
}

.credit-input-wrap {
	position: relative;
	display: flex;
	align-items: center;
}

.form-input {
	width: 100%;
	padding: 0.625rem 0.875rem;
	font-size: 1rem;
	color: var(--ql-text);
	background: var(--ql-bg, var(--ql-surface));
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
	box-sizing: border-box;
}

.form-input:focus {
	outline: none;
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px rgba(15, 110, 92, 0.15);
}

.credit-input {
	padding-right: 4.5rem;
	font-weight: 600;
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

/* Hide number input spinners */
.credit-input::-webkit-outer-spin-button,
.credit-input::-webkit-inner-spin-button {
	-webkit-appearance: none;
	margin: 0;
}

.credit-input[type="number"] {
	-moz-appearance: textfield;
}

.credit-suffix {
	position: absolute;
	right: 0.875rem;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	pointer-events: none;
}

.field-error {
	font-size: 0.75rem;
	color: #ef4444;
	margin: 0;
}

/* Quick Select */
.quick-select {
	display: flex;
	gap: 0.5rem;
	flex-wrap: wrap;
}

.preset-btn {
	padding: 0.375rem 0.875rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.preset-btn:hover {
	border-color: var(--ql-accent);
	color: var(--ql-accent);
}

.preset-btn.active {
	background-color: var(--ql-accent-soft);
	border-color: var(--ql-accent);
	color: var(--ql-accent);
}

/* Gateway Selection */
.gateway-grid {
	display: flex;
	gap: 0.75rem;
}

.gateway-card {
	flex: 1;
	display: flex;
	align-items: center;
	gap: 0.75rem;
	padding: 0.875rem 1rem;
	border: 2px solid var(--ql-border);
	border-radius: 0.75rem;
	cursor: pointer;
	transition: all 0.15s ease;
	background: var(--ql-surface);
}

.gateway-card:hover {
	border-color: var(--ql-accent);
}

.gateway-card.selected {
	border-color: var(--ql-accent);
	background: var(--ql-subtle);
	box-shadow: 0 0 0 3px rgba(15, 110, 92, 0.15);
}

.radio-outer {
	width: 1.125rem;
	height: 1.125rem;
	border: 2px solid var(--ql-border);
	border-radius: 50%;
	display: flex;
	align-items: center;
	justify-content: center;
	flex-shrink: 0;
	transition: border-color 0.15s ease;
}

.gateway-card.selected .radio-outer {
	border-color: var(--ql-accent);
}

.radio-inner {
	width: 0.5rem;
	height: 0.5rem;
	background-color: var(--ql-accent);
	border-radius: 50%;
}

.gateway-info {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.gateway-name {
	font-size: 0.9375rem;
	font-weight: 500;
	color: var(--ql-text);
}

.gateway-currency {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}
</style>
