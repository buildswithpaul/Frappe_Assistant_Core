<template>
	<div v-if="plan" class="confirm-backdrop" @click.self="$emit('cancel')">
		<div class="confirm-modal" role="dialog" aria-modal="true" :aria-label="title">
			<button class="close-btn" type="button" @click="$emit('cancel')" aria-label="Close">
				<svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
					<path
						d="M5 5l10 10M15 5L5 15"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
					/>
				</svg>
			</button>

			<h3 class="title">{{ title }}</h3>

			<div class="summary">
				<div class="summary-row">
					<span class="summary-label">{{ planLabel }} plan</span>
					<span class="summary-amount">{{ priceDisplay }}</span>
				</div>
				<div class="summary-row meta">
					<span>{{ cycleLabel }} via {{ gatewayLabel }}</span>
					<span class="period">{{ period }}</span>
				</div>
			</div>

			<div class="billing-row">
				<span class="billing-label">Billing to:</span>
				<span class="billing-email">{{ billingEmail || "Add billing details" }}</span>
				<button class="link-btn" type="button" @click="$emit('edit-billing')">
					{{ billingEmail ? "Edit" : "Add details" }}
				</button>
			</div>

			<fieldset v-if="showMethodPicker" class="method-picker">
				<legend class="method-legend">Payment method</legend>
				<label class="method-option" :class="{ selected: paymentMethod === 'upi' }">
					<input
						v-model="paymentMethod"
						type="radio"
						name="faco-payment-method"
						value="upi"
					/>
					<span class="method-body">
						<span class="method-title">
							UPI Autopay
							<span class="method-badge">Recommended</span>
						</span>
						<span class="method-sub">
							Authorize once via your UPI app — Google Pay, PhonePe, Paytm.
						</span>
					</span>
				</label>
				<label class="method-option" :class="{ selected: paymentMethod === 'card' }">
					<input
						v-model="paymentMethod"
						type="radio"
						name="faco-payment-method"
						value="card"
					/>
					<span class="method-body">
						<span class="method-title">Card</span>
						<span class="method-sub">
							Authorize a credit or debit card for recurring debits.
						</span>
					</span>
				</label>
			</fieldset>

			<div v-if="pricingLoading" class="breakdown loading">Calculating taxes…</div>
			<div v-else-if="pricingBreakdown" class="breakdown">
				<div class="breakdown-row">
					<span>Subtotal</span>
					<span>{{ formatAmount(pricingBreakdown.base) }}</span>
				</div>
				<div v-for="c in pricingBreakdown.components" :key="c.name" class="breakdown-row">
					<span>{{ c.name }} @ {{ formatRate(c.rate_percent) }}%</span>
					<span>{{ formatAmount(c.amount) }}</span>
				</div>
				<div class="breakdown-divider"></div>
				<div class="breakdown-row total">
					<span>Total due today</span>
					<span>{{ formatAmount(pricingBreakdown.total) }}</span>
				</div>
			</div>
			<div v-else-if="pricingError" class="breakdown error">
				{{ pricingError }}
			</div>

			<p class="disclosure">{{ disclosure }}</p>

			<HostedCheckoutNotice />

			<div class="actions">
				<button class="btn ghost" type="button" @click="$emit('cancel')">Cancel</button>
				<button
					class="btn primary"
					type="button"
					:disabled="!billingEmail || authorizing || pricingLoading"
					@click="onConfirm"
				>
					<span v-if="authorizing">Processing…</span>
					<span v-else-if="pricingBreakdown">
						Authorize &amp; Pay {{ formatAmount(pricingBreakdown.total) }}
					</span>
					<span v-else>Authorize &amp; Pay</span>
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { api } from "@/api/client";
import HostedCheckoutNotice from "./HostedCheckoutNotice.vue";

const props = defineProps({
	plan: { type: Object, default: null },
	priceMeta: { type: Object, default: null },
	billingCycle: { type: String, default: "monthly" },
	billingDetails: { type: Object, default: null },
	authorizing: { type: Boolean, default: false },
});

const emit = defineEmits(["confirm", "cancel", "edit-billing"]);

const pricingBreakdown = ref(null);
const pricingLoading = ref(false);
const pricingError = ref(null);

// Razorpay tokenizes one instrument per recurring authorization order, so
// the user picks UPI Autopay or Card before the widget opens. India only —
// USD recurring is card-only.
const paymentMethod = ref("upi");

const isInr = computed(() => {
	const c = pricingBreakdown.value?.currency || props.priceMeta?.currency;
	return c === "INR";
});

const showMethodPicker = computed(() => isInr.value);

function onConfirm() {
	const method = isInr.value ? paymentMethod.value : "card";
	emit("confirm", { plan: props.plan, paymentMethod: method });
}

const planLabel = computed(() => props.plan?.display_name || props.plan?.name || "");

const title = computed(() => `Confirm your ${planLabel.value} subscription`);

const cycleLabel = computed(() =>
	props.billingCycle === "annual" ? "Billed yearly" : "Billed monthly"
);

const period = computed(() => (props.billingCycle === "annual" ? "/year" : "/month"));

const gatewayLabel = computed(() => {
	const gw = props.priceMeta?.gateway || "razorpay";
	return gw === "razorpay" ? "Razorpay" : "Stripe";
});

const priceDisplay = computed(() => {
	if (!props.priceMeta || props.priceMeta.kind !== "amount") return "—";
	return `${props.priceMeta.symbol}${Number(props.priceMeta.amount).toLocaleString()}`;
});

const billingEmail = computed(() => props.billingDetails?.billing_email || null);

const currencySymbol = computed(() => {
	const c = pricingBreakdown.value?.currency || props.priceMeta?.currency;
	if (c === "INR") return "₹";
	if (c === "USD") return "$";
	if (c === "EUR") return "€";
	if (c === "GBP") return "£";
	return props.priceMeta?.symbol || "";
});

function formatAmount(value) {
	if (value == null) return "—";
	return `${currencySymbol.value}${Number(value).toLocaleString(undefined, {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	})}`;
}

function formatRate(rate) {
	if (rate == null) return "0";
	// Trim trailing zeros ("9.00" → "9", "9.50" → "9.5").
	return Number(rate).toString();
}

// Fetch the tax-inclusive breakdown whenever the modal opens on a new plan.
// We skip the call when the plan is not a billable plan (Free / Enterprise).
watch(
	() => [props.plan?.id || props.plan?.name, props.billingCycle],
	async ([planId, cycle]) => {
		pricingBreakdown.value = null;
		pricingError.value = null;
		if (!props.plan || !planId) return;
		const id = planId.toLowerCase();
		if (id === "free" || id === "enterprise") return;
		pricingLoading.value = true;
		try {
			const result = await api.billing.previewPlanPricing(planId, cycle);
			if (result?.success && result.pricing) {
				pricingBreakdown.value = result.pricing;
			} else {
				pricingError.value = result?.error || "Unable to compute taxes.";
			}
		} catch (e) {
			pricingError.value = e?.message || "Unable to compute taxes.";
		} finally {
			pricingLoading.value = false;
		}
	},
	{ immediate: true }
);

// Mandate copy varies by currency AND chosen instrument. UPI Autopay uses
// NPCI's UPI mandate rails; card recurring uses card-on-file. Picking the
// right language matters — NACH eMandate (a separate, bank-debit rail)
// was the wrong word here for both UPI and card.
const disclosure = computed(() => {
	const meta = props.priceMeta;
	const cycle = props.billingCycle === "annual" ? "every year" : "every month";
	if (!meta || meta.kind !== "amount") {
		return "Please contact sales to set up this subscription.";
	}
	// Prefer the tax-inclusive total if we have it; fall back to the
	// sticker price if the preview call hasn't resolved yet.
	const amount = pricingBreakdown.value
		? formatAmount(pricingBreakdown.value.total)
		: `${meta.symbol}${Number(meta.amount).toLocaleString()}`;
	if (meta.currency === "INR") {
		if (paymentMethod.value === "upi") {
			return (
				`By clicking Authorize & Pay, you pay ${amount} today and ` +
				`authorize Razorpay to debit your UPI account ${cycle} ` +
				`thereafter under UPI Autopay. You can cancel anytime from ` +
				`Billing settings — your access continues until the end of ` +
				`the paid period.`
			);
		}
		return (
			`By clicking Authorize & Pay, you pay ${amount} today and ` +
			`authorize Razorpay to charge the same card ${cycle} thereafter. ` +
			`You can cancel anytime from Billing settings — your access ` +
			`continues until the end of the paid period.`
		);
	}
	return (
		`By clicking Authorize & Pay, you pay ${amount} today and ` +
		`authorize Razorpay to charge the same ${cycle} thereafter. ` +
		`Razorpay manages the recurring schedule on our behalf. You can ` +
		`cancel anytime from Billing settings — your access continues until ` +
		`the end of the paid period.`
	);
});
</script>

<style scoped>
.confirm-backdrop {
	position: fixed;
	inset: 0;
	background: rgba(15, 23, 42, 0.55);
	backdrop-filter: blur(4px);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1000;
	padding: 1rem;
}

.confirm-modal {
	position: relative;
	width: 100%;
	max-width: 480px;
	background: var(--ql-surface, var(--ql-bg));
	border: 1px solid var(--ql-border);
	border-radius: 1rem;
	padding: 1.75rem 1.5rem 1.5rem;
	box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.35);
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

.close-btn {
	position: absolute;
	top: 0.75rem;
	right: 0.75rem;
	width: 2rem;
	height: 2rem;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	cursor: pointer;
	border-radius: 0.5rem;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	transition: background-color 0.15s ease;
}

.close-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

.close-btn svg {
	width: 1rem;
	height: 1rem;
}

.title {
	margin: 0;
	font-size: 1.0625rem;
	font-weight: 600;
	color: var(--ql-text);
	padding-right: 1.5rem;
}

.summary {
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.625rem;
	padding: 0.875rem 1rem;
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}

.summary-row {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	gap: 0.5rem;
}

.summary-label {
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
}

.summary-amount {
	font-size: 1.25rem;
	font-weight: 700;
	color: var(--ql-text);
	letter-spacing: -0.01em;
}

.summary-row.meta {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.summary-row.meta .period {
	font-weight: 500;
}

.billing-row {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	font-size: 0.8125rem;
}

.billing-label {
	color: var(--ql-text-muted);
}

.billing-email {
	color: var(--ql-text);
	font-weight: 500;
	flex: 1;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.link-btn {
	background: transparent;
	border: none;
	color: var(--ql-accent);
	font-size: 0.8125rem;
	font-weight: 500;
	cursor: pointer;
	padding: 0;
}

.link-btn:hover {
	text-decoration: underline;
}

.method-picker {
	border: none;
	padding: 0;
	margin: 0;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.method-legend {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	letter-spacing: 0.04em;
	text-transform: uppercase;
	padding: 0;
	margin-bottom: 0.125rem;
}

.method-option {
	display: flex;
	align-items: flex-start;
	gap: 0.625rem;
	padding: 0.6875rem 0.875rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.625rem;
	cursor: pointer;
	transition: border-color 0.15s ease, background-color 0.15s ease;
	background: var(--ql-bg);
}

.method-option:hover {
	background: var(--ql-subtle);
}

.method-option.selected {
	border-color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.method-option input[type="radio"] {
	margin-top: 0.125rem;
	accent-color: var(--ql-accent);
	cursor: pointer;
}

.method-body {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	flex: 1;
	min-width: 0;
}

.method-title {
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
}

.method-badge {
	font-size: 0.6875rem;
	font-weight: 600;
	letter-spacing: 0.02em;
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
	padding: 0.125rem 0.4375rem;
	border-radius: 999px;
}

.method-sub {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	line-height: 1.4;
}

.breakdown {
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.625rem;
	padding: 0.75rem 1rem;
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
	font-size: 0.875rem;
	color: var(--ql-text);
}

.breakdown.loading,
.breakdown.error {
	color: var(--ql-text-muted);
	font-size: 0.8125rem;
	text-align: center;
	padding: 0.875rem 1rem;
}

.breakdown.error {
	color: var(--ql-danger, #dc2626);
}

.breakdown-row {
	display: flex;
	justify-content: space-between;
	align-items: baseline;
	gap: 1rem;
}

.breakdown-row > :first-child {
	color: var(--ql-text-muted);
}

.breakdown-row.total {
	font-weight: 700;
	font-size: 0.9375rem;
}

.breakdown-row.total > :first-child {
	color: var(--ql-text);
}

.breakdown-divider {
	height: 1px;
	background: var(--ql-border);
	margin: 0.125rem 0;
}

.disclosure {
	margin: 0;
	font-size: 0.8125rem;
	line-height: 1.5;
	color: var(--ql-text-muted);
	background: var(--ql-accent-soft);
	border-left: 3px solid var(--ql-accent);
	padding: 0.75rem 0.875rem;
	border-radius: 0.375rem;
}

.actions {
	display: flex;
	justify-content: flex-end;
	gap: 0.5rem;
	margin-top: 0.25rem;
}

.btn {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 600;
	border-radius: 0.5rem;
	cursor: pointer;
	border: 1px solid transparent;
	transition: opacity 0.15s ease, background-color 0.15s ease;
}

.btn.primary {
	background: var(--ql-accent);
	color: white;
}

.btn.primary:hover:not(:disabled) {
	opacity: 0.92;
}

.btn.primary:disabled {
	opacity: 0.55;
	cursor: not-allowed;
}

.btn.ghost {
	background: transparent;
	color: var(--ql-text);
	border-color: var(--ql-border);
}

.btn.ghost:hover {
	background: var(--ql-subtle);
}
</style>
