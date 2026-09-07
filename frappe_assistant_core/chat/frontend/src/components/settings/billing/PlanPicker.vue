<template>
	<div class="plan-picker">
		<div class="picker-header">
			<div>
				<h3 class="picker-title">Choose your plan</h3>
				<p v-if="planChangesLocked" class="picker-subtitle">
					Plan changes are paused while cancellation is scheduled. Click
					<strong>Keep my plan</strong> above if you want to stay or switch plans.
				</p>
				<p v-else-if="onFreePlan" class="picker-subtitle">
					You're on the Free plan. Pick a paid plan below to unlock more capacity.
				</p>
			</div>
			<div class="cycle-toggle" role="tablist" aria-label="Billing cycle">
				<button
					type="button"
					role="tab"
					:aria-selected="billingCycle === 'monthly'"
					class="cycle-btn"
					:class="{ active: billingCycle === 'monthly' }"
					@click="$emit('update:billingCycle', 'monthly')"
				>
					Monthly
				</button>
				<button
					type="button"
					role="tab"
					:aria-selected="billingCycle === 'annual'"
					class="cycle-btn"
					:class="{ active: billingCycle === 'annual' }"
					@click="$emit('update:billingCycle', 'annual')"
				>
					Annual
					<span class="save-badge">Save 17%</span>
				</button>
			</div>
		</div>

		<div class="plans-grid" v-if="cards.length">
			<article
				v-for="card in cards"
				:key="card.id"
				class="plan-card"
				:class="{
					current: card.isCurrent,
					popular: card.isPopular,
					enterprise: card.isEnterprise,
				}"
			>
				<div v-if="card.isPopular" class="popular-ribbon">Most Popular</div>
				<span v-if="card.isCurrent" class="active-pill">Active</span>

				<div class="card-head">
					<h4 class="plan-name">{{ card.displayName }}</h4>
				</div>

				<div class="price-block">
					<template v-if="card.priceMeta.kind === 'amount'">
						<div class="price-row">
							<span class="price-symbol">{{ card.priceMeta.symbol }}</span>
							<span class="price-amount">{{
								formatAmount(card.priceMeta.amount)
							}}</span>
						</div>
						<span class="price-period">{{ card.priceMeta.period }}</span>
						<span v-if="card.seatLine" class="seat-line">{{ card.seatLine }}</span>
					</template>
					<template v-else-if="card.priceMeta.kind === 'custom'">
						<div class="price-row custom">
							<span class="price-amount custom">Custom</span>
						</div>
						<span class="price-period">Tailored to your team</span>
					</template>
					<template v-else>
						<div class="price-row">
							<span class="price-amount unavailable">Contact sales</span>
						</div>
						<span class="price-period">{{ card.priceMeta.reason }}</span>
					</template>
				</div>

				<ul class="features" v-if="card.features.length">
					<li v-for="feature in card.features" :key="feature">
						<svg class="check" viewBox="0 0 20 20" fill="none" aria-hidden="true">
							<path
								d="M5 10l3.5 3.5L15 7"
								stroke="currentColor"
								stroke-width="2"
								stroke-linecap="round"
								stroke-linejoin="round"
							/>
						</svg>
						<span>{{ feature }}</span>
					</li>
				</ul>

				<button
					type="button"
					class="cta"
					:class="{
						secondary: card.isCurrent || card.isEnterprise,
						disabled: card.disabled,
					}"
					:disabled="card.disabled || upgrading"
					@click="onCardAction(card)"
				>
					{{ card.ctaLabel }}
				</button>

				<p v-if="card.priceMeta.isPerUser" class="seat-hint">
					Add or remove seats in
					<button type="button" class="seat-link" @click="$emit('manage-seats')">
						Settings → Users
					</button>
				</p>

				<p v-if="card.billingNote" class="billing-note">{{ card.billingNote }}</p>
			</article>
		</div>

		<p v-else class="empty-text">No plans available right now.</p>
	</div>
</template>

<script setup>
import { computed } from "vue";

import { getSeatSummary } from "../../../composables/_billing/billingFormatters";

const props = defineProps({
	availablePlans: { type: Array, default: () => [] },
	currentPlan: { type: String, required: true },
	billingCycle: { type: String, required: true },
	upgrading: { type: Boolean, default: false },
	/** True only for cancel→Free (not paid-to-paid scheduled downgrades). */
	planChangesLocked: { type: Boolean, default: false },
	/**
	 * A paid-to-paid change is queued for period end. The current card's CTA
	 * then undoes it, so it has to say so rather than read "Manage".
	 */
	hasScheduledChange: { type: Boolean, default: false },
	getPlanPrice: { type: Function, required: true },
	getPlanPriceMeta: { type: Function, required: true },
	getPlanActionText: { type: Function, required: true },
	/**
	 * `get_user_limit_status` payload, or null when the seat count is unknown.
	 * That endpoint is System Manager only, so members see the seat minimum
	 * rather than a count we could not read.
	 */
	seatStatus: { type: Object, default: null },
});

const emit = defineEmits([
	"update:billingCycle",
	"upgrade",
	"manage-seats",
	"manage-subscription",
]);

const POPULAR_PLAN_IDS = ["team", "pro"];
const HIDDEN_PLAN_IDS = ["free", "development"];

function planId(plan) {
	return (plan.id || plan.name || "").toLowerCase();
}

function isEnterprise(plan) {
	return planId(plan) === "enterprise";
}

function gatewayLabel(meta) {
	if (meta.kind !== "amount") return null;
	const display = meta.gateway === "razorpay" ? "Razorpay" : "Stripe";
	return `Billed in ${meta.currency} via ${display}`;
}

function ctaLabelFor(plan, isCurrent) {
	if (props.planChangesLocked && !isEnterprise(plan)) {
		return isCurrent ? "Current Plan" : "Unavailable";
	}
	// One label used to cover both states, and only one of them did anything:
	// with a change queued the CTA cancels it, otherwise `handleUpgrade`
	// returns on `planId === currentPlan` and the click was silent.
	if (isCurrent) return props.hasScheduledChange ? "Keep This Plan" : "Manage";
	if (isEnterprise(plan)) return "Talk to sales";
	return props.getPlanActionText(plan);
}

/**
 * The current plan has nothing to buy, so its CTA manages the subscription
 * instead — payment method and cancellation, which live on the Settings tab.
 * Undoing a queued change stays on the upgrade path, where
 * `handleUpgrade` already routes it to `handleCancelScheduledChange`.
 */
function onCardAction(card) {
	if (card.isCurrent && !props.hasScheduledChange && !card.isEnterprise) {
		emit("manage-subscription");
		return;
	}
	emit("upgrade", card.plan);
}

const onFreePlan = computed(() => (props.currentPlan || "").toLowerCase() === "free");

const cards = computed(() => {
	return props.availablePlans
		.filter((plan) => !HIDDEN_PLAN_IDS.includes(planId(plan)))
		.map((plan) => {
			const id = planId(plan);
			const isCurrent =
				plan.action === "current" || id === (props.currentPlan || "").toLowerCase();
			const enterprise = isEnterprise(plan);
			const popular = !enterprise && POPULAR_PLAN_IDS.includes(id);
			const priceMeta = props.getPlanPriceMeta(plan);
			const features = (plan.features || []).slice(0, 4);
			// Freeze CTAs while cancel→Free is pending. Paid scheduled
			// downgrades still need "Keep This Plan" on the current card,
			// so we only lock on planChangesLocked — not on isCurrent alone.
			const disabled =
				priceMeta.kind === "unavailable" || (props.planChangesLocked && !enterprise);

			return {
				id: plan.id || plan.name,
				plan,
				displayName: plan.display_name || plan.name,
				isCurrent,
				isEnterprise: enterprise,
				isPopular: popular,
				priceMeta,
				seatLine: seatLineFor(priceMeta, isCurrent),
				features,
				ctaLabel: ctaLabelFor(plan, isCurrent),
				disabled: !!disabled,
				billingNote: enterprise ? "Custom terms" : gatewayLabel(priceMeta),
			};
		});
});

function formatAmount(amount) {
	if (amount == null) return "--";
	return Number(amount).toLocaleString();
}

/**
 * The sentence under a per-user price, so the seat rate is never shown without
 * the bill it adds up to. Null for flat plans, which need no such explanation.
 */
function seatLineFor(priceMeta, isCurrent) {
	const summary = getSeatSummary(priceMeta, props.seatStatus, isCurrent);
	if (!summary) return null;

	const money = (amount) => `${priceMeta.symbol}${formatAmount(amount)}`;
	const cycle = props.billingCycle === "annual" ? "yr" : "mo";
	const seats = (n) => `${n} seat${n === 1 ? "" : "s"}`;

	if (summary.kind === "minimum") {
		return `From ${money(summary.total)}/${cycle} · ${seats(summary.seats)} minimum`;
	}
	return `${seats(summary.seats)} · ${money(summary.total)}/${cycle}`;
}
</script>

<style scoped>
/* The grid below sizes off THIS box, not the viewport. Settings puts ~580px of
   fixed chrome to the left of it (260px app nav + 240px menu pane + 80px inner
   padding), so a viewport breakpoint describes a width this element never has:
   at a 1025px viewport the old rules asked for four columns inside 445px. */
.plan-picker {
	display: flex;
	flex-direction: column;
	gap: 1.25rem;
	container-type: inline-size;
}

.picker-header {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 1rem;
	flex-wrap: wrap;
}

.picker-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}

.picker-subtitle {
	margin: 0.375rem 0 0;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.cycle-toggle {
	display: inline-flex;
	gap: 0.25rem;
	padding: 0.25rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.625rem;
}

.cycle-btn {
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: color 0.15s ease, background-color 0.15s ease;
}

.cycle-btn:hover {
	color: var(--ql-text);
}

.cycle-btn.active {
	background: var(--ql-surface);
	color: var(--ql-text);
	box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.save-badge {
	padding: 0.125rem 0.5rem;
	font-size: 0.6875rem;
	font-weight: 600;
	color: #16a34a;
	background: rgba(34, 197, 94, 0.12);
	border-radius: 9999px;
}

.plans-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: 1rem;
}

.plan-card {
	position: relative;
	display: flex;
	flex-direction: column;
	gap: 1rem;
	padding: 1.5rem 1.25rem 1.25rem;
	background: var(--ql-surface, var(--ql-bg));
	border: 1px solid var(--ql-border);
	border-radius: 0.875rem;
	transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
	min-height: 360px;
}

.plan-card:hover:not(.current) {
	transform: translateY(-2px);
	box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
	border-color: var(--ql-accent);
}

.plan-card.popular {
	border-color: var(--ql-accent);
	border-top: 3px solid var(--ql-accent);
	padding-top: 1.5rem;
}

.plan-card.current {
	border-color: var(--ql-gold);
	box-shadow: 0 0 0 1px var(--ql-gold);
	background: var(--ql-gold-soft);
}

.plan-card.enterprise {
	background: linear-gradient(
		180deg,
		rgba(245, 158, 11, 0.04) 0%,
		var(--ql-surface, var(--ql-bg)) 100%
	);
	border-color: rgba(245, 158, 11, 0.35);
}

.popular-ribbon {
	position: absolute;
	top: -0.75rem;
	left: 50%;
	transform: translateX(-50%);
	padding: 0.25rem 0.875rem;
	font-size: 0.6875rem;
	font-weight: 700;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: white;
	background: var(--ql-accent);
	border-radius: 9999px;
	white-space: nowrap;
	box-shadow: 0 4px 10px rgba(15, 110, 92, 0.35);
}

.active-pill {
	position: absolute;
	top: 0.875rem;
	right: 0.875rem;
	padding: 0.125rem 0.5rem;
	font-size: 0.6875rem;
	font-weight: 600;
	color: var(--ql-gold);
	background: var(--ql-gold-soft);
	border: 1px solid var(--ql-gold);
	border-radius: 9999px;
	letter-spacing: 0.04em;
	text-transform: uppercase;
}

.card-head {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	/* A flex item defaults to min-width:auto and refuses to shrink below its
	   content, so a long plan name pushes out of the card rather than wrapping. */
	min-width: 0;
}

/* Only the current plan carries the absolutely-positioned "Active" pill, and it
   overlaps this row vertically — keep the name clear of it on that card alone. */
.plan-card.current .card-head {
	padding-right: 3.5rem;
}

.plan-name {
	margin: 0;
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
	letter-spacing: 0.01em;
	min-width: 0;
	overflow-wrap: anywhere;
}

.price-block {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
}

.price-row {
	display: flex;
	align-items: flex-start;
	gap: 0.125rem;
}

.price-symbol {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-top: 0.375rem;
}

.price-amount {
	font-size: 2rem;
	font-weight: 700;
	color: var(--ql-text);
	line-height: 1.1;
	letter-spacing: -0.01em;
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.price-amount.custom {
	font-size: 1.625rem;
}

.price-amount.unavailable {
	font-size: 1.125rem;
	color: var(--ql-text-muted);
	font-weight: 600;
}

.price-period {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin-top: 0.25rem;
}

/* Sits directly under the seat rate: the rate alone never tells a buyer what
   they will be charged, so the two always render together. */
.seat-line {
	display: block;
	margin-top: 0.375rem;
	font-size: 0.75rem;
	line-height: 1.4;
	color: var(--ql-text-secondary);
}

.features {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	flex: 1;
}

.features li {
	display: flex;
	align-items: flex-start;
	gap: 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text-muted, var(--ql-text-muted));
	line-height: 1.4;
}

.check {
	flex-shrink: 0;
	width: 1rem;
	height: 1rem;
	margin-top: 0.125rem;
	color: var(--ql-accent);
}

.cta {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 100%;
	padding: 0.625rem 1rem;
	font-size: 0.875rem;
	font-weight: 600;
	color: white;
	background: var(--ql-accent);
	border: 1px solid transparent;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: opacity 0.15s ease, background-color 0.15s ease;
}

.cta:hover:not(:disabled):not(.disabled) {
	background: var(--ql-accent-hover);
}

.cta.secondary {
	background: transparent;
	color: var(--ql-text);
	border-color: var(--ql-border);
}

.cta.secondary:hover:not(:disabled):not(.disabled) {
	border-color: var(--ql-accent);
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.cta:disabled,
.cta.disabled {
	cursor: default;
	opacity: 0.55;
}

.seat-hint {
	margin: 0 0 0.375rem;
	font-size: 0.6875rem;
	line-height: 1.5;
	color: var(--ql-text-muted);
	text-align: center;
}

.seat-link {
	padding: 0;
	border: 0;
	background: none;
	font: inherit;
	color: var(--ql-accent);
	text-decoration: underline;
	text-underline-offset: 2px;
	cursor: pointer;
}

.seat-link:hover {
	opacity: 0.8;
}

.billing-note {
	margin: 0;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	text-align: center;
	letter-spacing: 0.02em;
}

.empty-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	text-align: center;
	padding: 2rem 0;
}

/* Measured, not estimated: the widest price this renders is "₹1,79,988" at
   165px in 2rem tabular monospace. Four columns only clear that above ~1000px
   of container, so the type steps down before the columns do — otherwise a
   1440px desktop overflows by 2px, which it did long before container queries. */
@container (max-width: 1000px) {
	.price-amount {
		font-size: 1.75rem;
	}
}

/* Tiers keep a card's content box at ~163px or wider at every width. */
@container (max-width: 840px) {
	.plans-grid {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
}

@container (max-width: 620px) {
	.plans-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
}

@container (max-width: 400px) {
	.plans-grid {
		grid-template-columns: minmax(0, 1fr);
		gap: 0.75rem;
	}

	.picker-header {
		flex-direction: column;
		align-items: stretch;
	}

	.cycle-toggle {
		align-self: flex-start;
	}
}

/* Container queries need Safari 16; this project's build target is Safari 14,
   and older iPadOS is exactly the population that hit the original bug. These
   viewport thresholds are the container tiers above plus the ~580px of settings
   chrome (260px nav + 240px menu + 80px padding) that sits left of the grid. */
@supports not (container-type: inline-size) {
	@media (max-width: 1580px) {
		.price-amount {
			font-size: 1.75rem;
		}
	}

	@media (max-width: 1420px) {
		.plans-grid {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
	}

	@media (max-width: 1200px) {
		.plans-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	@media (max-width: 640px) {
		.plans-grid {
			grid-template-columns: minmax(0, 1fr);
			gap: 0.75rem;
		}

		.picker-header {
			flex-direction: column;
			align-items: stretch;
		}

		.cycle-toggle {
			align-self: flex-start;
		}
	}
}
</style>
