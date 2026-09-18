<template>
	<div class="billing-hero">
		<div class="hero-content">
			<!-- Plan Info (Left) -->
			<div class="hero-plan">
				<div class="plan-row">
					<h2 class="plan-name">{{ formatPlanName(currentPlan) }}</h2>
					<span
						v-if="cancelAtPeriodEnd"
						class="plan-badge badge-cancelling"
					>
						Cancelling
					</span>
					<span
						v-else
						class="plan-badge"
						:class="'badge-' + currentPlan.toLowerCase()"
					>
						{{ formatPlanName(currentPlan) }}
					</span>
				</div>
				<p class="plan-price" v-if="planPriceDisplay">{{ planPriceDisplay }}</p>
				<p class="plan-price" v-else-if="currentPlan.toLowerCase() === 'free'">Free</p>
				<p class="next-billing cancelling" v-if="cancelAtPeriodEnd && periodEndDate">
					Access until {{ periodEndDate }} — then Free plan
				</p>
				<p class="next-billing cancelling" v-else-if="cancelAtPeriodEnd">
					Access until end of billing period — then Free plan
				</p>
				<p class="next-billing" v-else-if="nextBillingDate">
					Next billing: {{ nextBillingDate }}
				</p>
			</div>

			<!-- Usage (Right) -->
			<div class="hero-usage" v-if="!quota?.is_unlimited">
				<div class="usage-ring-container">
					<svg class="usage-ring" viewBox="0 0 80 80">
						<circle
							class="ring-bg"
							cx="40"
							cy="40"
							r="34"
							fill="none"
							stroke-width="6"
						/>
						<circle
							class="ring-fill"
							cx="40"
							cy="40"
							r="34"
							fill="none"
							stroke-width="6"
							:stroke="usageBarColor"
							:stroke-dasharray="ringCircumference"
							:stroke-dashoffset="ringOffset"
							stroke-linecap="round"
							transform="rotate(-90 40 40)"
						/>
					</svg>
					<div class="ring-label">
						<span class="ring-percent">{{ Math.round(creditsPercentage) }}%</span>
					</div>
				</div>
				<div class="usage-details">
					<span class="usage-title">Credits Used</span>
					<span class="usage-numbers">
						{{ formatCredits(creditsUsed) }} / {{ formatCredits(creditsTotal) }}
					</span>
					<span class="usage-reset" v-if="usageResetDate"
						>Resets {{ usageResetDate }}</span
					>
				</div>
			</div>
			<div class="hero-usage" v-else>
				<div class="unlimited-badge">Unlimited</div>
				<span class="usage-title">Development Mode</span>
			</div>
		</div>

		<!-- Whatever the page wants to say about this billing period — today,
		     an unpaid renewal. Above the actions, because "Buy Credits" is not
		     the move while the last charge has not cleared. -->
		<div class="hero-slot"><slot /></div>

		<!-- Actions -->
		<div class="hero-actions">
			<button class="action-btn primary" @click="$emit('change-plan')">
				<svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
					/>
				</svg>
				Change Plan
			</button>
			<button class="action-btn secondary" @click="$emit('buy-credits')">
				<svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 6v6m0 0v6m0-6h6m-6 0H6"
					/>
				</svg>
				Buy Credits
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { formatPlanName } from "@/composables/useFormatters";

const props = defineProps({
	currentPlan: { type: String, required: true },
	subscription: { type: Object, default: () => ({}) },
	quota: { type: Object, default: null },
	creditsPercentage: { type: Number, default: 0 },
	usageBarColor: { type: String, default: "var(--ql-accent)" },
	usageResetDate: { type: String, default: null },
	cancelAtPeriodEnd: { type: Boolean, default: false },
	periodEndDate: { type: String, default: null },
});

defineEmits(["change-plan", "buy-credits"]);

const CURRENCY_SYMBOLS = { INR: "₹", USD: "$", EUR: "€", GBP: "£" };

const planPriceDisplay = computed(() => {
	const plan = props.currentPlan.toLowerCase();
	if (plan === "free" || plan === "enterprise" || plan === "development") return null;

	// Prefer the backend-computed estimated monthly bill — handles
	// per-user plans (seats × per-user price) AND flat plans, with GST
	// folded in when the tenant has billing config. Falls back to the
	// flat plan price for older AR backends that don't ship the field.
	const estimate = props.quota?.estimated_monthly_bill;
	const currency =
		estimate?.currency || props.subscription?.currency || props.quota?.currency || "USD";
	const symbol = CURRENCY_SYMBOLS[currency] || "";

	if (estimate && (estimate.total || estimate.subtotal)) {
		const amount = estimate.total || estimate.subtotal;
		const taxSuffix = estimate.tax_estimated ? "" : " + taxes";
		return `${symbol}${Number(amount).toLocaleString()}/month${taxSuffix}`;
	}

	// Prefer the currency-correct sticker from AR. Only fall back to the
	// legacy USD field when we are actually displaying USD — otherwise an
	// Indian tenant with a missing plan_price would still show "$60".
	const price =
		props.quota?.plan_price ||
		(currency === "USD" ? props.quota?.plan_price_usd : null) ||
		props.subscription?.price;
	if (!price) return null;
	const period = props.subscription?.billing_cycle === "annual" ? "/year" : "/month";
	return `${symbol}${Number(price).toLocaleString()}${period}`;
});

const nextBillingDate = computed(() => {
	const date = props.subscription?.current_period_end || props.subscription?.next_billing_date;
	if (!date) return null;
	return new Date(date).toLocaleDateString("en-US", {
		month: "short",
		day: "numeric",
		year: "numeric",
	});
});

const creditsUsed = computed(() => {
	return Math.round(props.quota?.credits_used || props.quota?.quota_used || 0);
});

const creditsTotal = computed(() => {
	return props.quota?.credit_quota || props.quota?.quota_total || 0;
});

const ringCircumference = 2 * Math.PI * 34; // r = 34
const ringOffset = computed(() => {
	const pct = Math.min(props.creditsPercentage, 100) / 100;
	return ringCircumference * (1 - pct);
});

function formatCredits(val) {
	if (!val) return "0";
	return Number(val).toLocaleString();
}
</script>

<style scoped>
/* Spacing hangs off the child, not the wrapper: a v-if'd slot still leaves a
   comment node behind, so `:empty` never matches and a margin on the wrapper
   would reserve a gap for a notice that is not there. A comment is not an
   element, so `> *` matches nothing when nothing renders. */
.hero-slot > * {
	margin-top: 1rem;
}

.billing-hero {
	padding: 1.5rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
}

.hero-content {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 1.5rem;
}

.hero-plan {
	flex: 1;
}

.plan-row {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	margin-bottom: 0.25rem;
}

.plan-name {
	font-size: 1.25rem;
	font-weight: 700;
	color: var(--ql-text);
	margin: 0;
}

.plan-badge {
	padding: 0.1875rem 0.5rem;
	font-size: 0.6875rem;
	font-weight: 600;
	text-transform: uppercase;
	border-radius: 9999px;
	letter-spacing: 0.04em;
}

.badge-free,
.badge-development {
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
}
/* Paid (current) plan badges carry the gold accent reserved for money/consequence. */
.badge-individual,
.badge-starter,
.badge-team,
.badge-pro,
.badge-organization,
.badge-enterprise {
	background: var(--ql-gold-soft);
	color: var(--ql-gold);
}

.badge-cancelling {
	background: rgba(245, 158, 11, 0.15);
	color: #d97706;
}

.plan-price {
	font-size: 1.5rem;
	font-weight: 700;
	color: var(--ql-text);
	margin: 0.25rem 0 0;
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.next-billing {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin: 0.375rem 0 0;
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.next-billing.cancelling {
	color: #d97706;
	font-weight: 500;
	font-family: inherit;
}

/* Usage Ring */
.hero-usage {
	display: flex;
	align-items: center;
	gap: 0.875rem;
	flex-shrink: 0;
}

.usage-ring-container {
	position: relative;
	width: 72px;
	height: 72px;
}

.usage-ring {
	width: 100%;
	height: 100%;
}

.ring-bg {
	stroke: var(--ql-border);
}

.ring-fill {
	transition: stroke-dashoffset 0.6s ease, stroke 0.3s ease;
}

.ring-label {
	position: absolute;
	inset: 0;
	display: flex;
	align-items: center;
	justify-content: center;
}

.ring-percent {
	font-size: 0.9375rem;
	font-weight: 700;
	color: var(--ql-text);
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.usage-details {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
}

.usage-title {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
}

.usage-numbers {
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.usage-reset {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.unlimited-badge {
	padding: 0.375rem 0.75rem;
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
	border-radius: 9999px;
}

/* Actions */
.hero-actions {
	display: flex;
	gap: 0.625rem;
	margin-top: 1.25rem;
	padding-top: 1.25rem;
	border-top: 1px solid var(--ql-border);
}

.action-btn {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
	border: none;
}

.action-btn.primary {
	background: var(--ql-accent);
	color: white;
}

.action-btn.primary:hover {
	opacity: 0.9;
}

.action-btn.secondary {
	background: var(--ql-bg);
	color: var(--ql-text);
	border: 1px solid var(--ql-border);
}

.action-btn.secondary:hover {
	border-color: var(--ql-accent);
	color: var(--ql-accent);
}

.btn-icon {
	width: 0.875rem;
	height: 0.875rem;
}

/* Responsive */
@media (max-width: 640px) {
	.hero-content {
		flex-direction: column;
		gap: 1.25rem;
	}

	.hero-usage {
		width: 100%;
	}

	.hero-actions {
		flex-direction: column;
	}

	.action-btn {
		justify-content: center;
	}
}
</style>
