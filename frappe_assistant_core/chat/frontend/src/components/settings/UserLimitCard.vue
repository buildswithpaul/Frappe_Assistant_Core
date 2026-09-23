<template>
	<div
		class="limit-card"
		:class="{ 'at-limit': isAtLimit, 'near-limit': isNearLimit && !isAtLimit }"
	>
		<div class="limit-header">
			<div class="limit-info">
				<span class="limit-label">User Limit</span>
				<span class="limit-value">
					<template v-if="isSeatPlan">
						{{ activeUsers }}
						<span class="limit-separator">of</span>
						{{ paidSeats }}
						<span class="limit-unit">seats assigned</span>
					</template>
					<template v-else>
						{{ userLimit?.active_users || 0 }}
						<span class="limit-separator">/</span>
						<template v-if="userLimit?.is_unlimited">&infin;</template>
						<template v-else>{{ userLimit?.max_users || 0 }}</template>
						<span class="limit-unit">users</span>
					</template>
				</span>
			</div>
			<span class="plan-badge" :class="'badge-' + (userLimit?.plan || 'free').toLowerCase()">
				{{ userLimit?.plan || "Free" }}
			</span>
		</div>

		<!-- Progress Bar (only for limited plans) -->
		<div class="limit-bar" v-if="!userLimit?.is_unlimited">
			<div
				class="limit-fill"
				:style="{ width: usagePercentage + '%' }"
				:class="{ 'fill-warning': isNearLimit, 'fill-danger': isAtLimit }"
			></div>
		</div>

		<!-- Warning Banner -->
		<div v-if="isAtLimit" class="limit-warning">
			<svg class="warning-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
				/>
			</svg>
			<span>User limit reached. Remove users or upgrade to add more.</span>
		</div>

		<!-- Credit pool info for Team plan -->
		<div v-if="creditsPerUser > 0" class="credit-pool-info">
			<span class="pool-label">Credit Pool</span>
			<span class="pool-value">
				{{ formatNumber(creditPool) }} credits
				<span class="pool-rate">({{ formatNumber(creditsPerUser) }} per user)</span>
			</span>
		</div>

		<!-- Seat billing breakdown -->
		<div v-if="isSeatPlan && extraSeats > 0" class="purchased-seats-info">
			{{ minUsers }} included + {{ extraSeats }} additional seat{{
				extraSeats !== 1 ? "s" : ""
			}}
			<span class="seat-cost" v-if="pricePerUser"
				>({{ formatPrice(extraSeats * pricePerUser) }}/mo)</span
			>
		</div>

		<!-- Estimated next monthly bill — total cost for the current
		     seat count + GST (when computable). Anchors admins to the
		     total spend before they make seat-count changes. -->
		<div v-if="hasEstimate" class="monthly-estimate">
			<div class="estimate-row">
				<span class="estimate-label">Estimated next monthly bill</span>
				<span class="estimate-value">
					{{ formatPrice(estimatedMonthlyBill.total || estimatedMonthlyBill.subtotal) }}
					<span v-if="!estimatedMonthlyBill.tax_estimated" class="estimate-suffix"
						>+ taxes</span
					>
				</span>
			</div>
			<div
				v-if="estimatedMonthlyBill.is_per_user && estimatedMonthlyBill.billable_seats"
				class="estimate-breakdown"
			>
				{{ estimatedMonthlyBill.billable_seats }}
				{{ estimatedMonthlyBill.billable_seats === 1 ? "user" : "users" }}
				&times;
				{{ formatPrice(pricePerUser) }}
				<template v-if="estimatedMonthlyBill.tax_estimated">
					+ {{ formatPrice(estimatedMonthlyBill.tax) }} tax
				</template>
			</div>
			<div v-else-if="!estimatedMonthlyBill.tax_estimated" class="estimate-breakdown">
				Final taxes calculated at checkout based on your billing address.
			</div>
		</div>

		<!-- Per-seat pricing notice — surfaced on per-user plans even
		     before the seat cap is hit, so admins know what each new
		     user will cost before they click Add. -->
		<div
			v-if="pricePerUser && activeUsers >= minUsers && !isAtLimit"
			class="seat-pricing-notice"
		>
			<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<span>
				Each additional user costs
				<strong>{{ formatPrice(pricePerUser) }}/month</strong>
				(price and credits both prorated for the current cycle). You'll see the exact
				charge before confirming.
			</span>
		</div>

		<!-- Upgrade hint for limited plans -->
		<div v-if="!userLimit?.is_unlimited && !isAtLimit" class="upgrade-hint">
			<span
				>{{ userLimit?.remaining }} slot{{
					userLimit?.remaining !== 1 ? "s" : ""
				}}
				remaining</span
			>
			<template v-if="pricePerUser && activeUsers >= minUsers">
				<span class="hint-separator">•</span>
				<span>{{ formatPrice(pricePerUser) }}/user for additional seats</span>
			</template>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	userLimit: { type: Object, default: null },
	creditsPerUser: { type: Number, default: 0 },
	minUsers: { type: Number, default: 1 },
	pricePerUser: { type: Number, default: 0 },
	currency: { type: String, default: "USD" },
	estimatedMonthlyBill: { type: Object, default: null },
	/** The tenant's actual credit pool, straight from the subscription. */
	creditQuota: { type: Number, default: 0 },
});

const hasEstimate = computed(() => {
	const est = props.estimatedMonthlyBill;
	return !!(est && (est.subtotal || est.total));
});

const CURRENCY_SYMBOLS = { INR: "₹", USD: "$", EUR: "€", GBP: "£" };

function formatPrice(value) {
	if (value == null) return "—";
	const sym = CURRENCY_SYMBOLS[props.currency] || "";
	const num = Number(value);
	// Whole rupees/dollars look cleaner without trailing zeros for the
	// per-seat price line; the seat purchase modal still shows two
	// decimals on the actual prorated charge.
	const formatted = Number.isInteger(num)
		? num.toLocaleString()
		: num.toLocaleString(undefined, {
				minimumFractionDigits: 2,
				maximumFractionDigits: 2,
		  });
	return `${sym}${formatted}`;
}

const isAtLimit = computed(() => {
	if (!props.userLimit || props.userLimit.is_unlimited) return false;
	return props.userLimit.remaining <= 0;
});

const isNearLimit = computed(() => {
	if (!props.userLimit || props.userLimit.is_unlimited) return false;
	const pct = (props.userLimit.active_users / props.userLimit.max_users) * 100;
	return pct >= 80;
});

const usagePercentage = computed(() => {
	if (!props.userLimit || props.userLimit.is_unlimited) return 0;
	return Math.min(100, (props.userLimit.active_users / props.userLimit.max_users) * 100);
});

// A plan that sells no seats has no paid_seats figure to show. Without this
// gate the header fell back to Math.max(headcount, minUsers) -- which is
// just the headcount again -- and invented a seat cap next to the real
// max_users the progress bar and "slots remaining" line already show.
const isSeatPlan = computed(() => !!props.userLimit?.is_per_user);

const activeUsers = computed(() => props.userLimit?.assigned_seats ?? props.userLimit?.active_users ?? 0);

// Seats the customer pays for. Deriving this from member rows hid the
// "additional seats" line entirely whenever a seat stood empty.
const paidSeats = computed(
	() => props.userLimit?.paid_seats ?? Math.max(activeUsers.value, props.minUsers),
);

const extraSeats = computed(() => Math.max(0, paidSeats.value - props.minUsers));

// The pool is whatever the subscription says it is. Recomputing it as
// credits_per_user × seats overstates every mid-cycle addition, which is
// granted a prorated share.
const creditPool = computed(() => props.creditQuota ?? 0);

function formatNumber(val) {
	if (!val) return "0";
	return Number(val).toLocaleString();
}
</script>

<style scoped>
.limit-card {
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 1rem;
}

.limit-card.near-limit {
	border-color: rgba(234, 179, 8, 0.5);
}

.limit-card.at-limit {
	border-color: rgba(239, 68, 68, 0.5);
	background: rgba(239, 68, 68, 0.02);
}

.limit-header {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	margin-bottom: 0.75rem;
}

.limit-info {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}

.limit-label {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.025em;
}

.limit-value {
	font-size: 1.5rem;
	font-weight: 600;
	color: var(--ql-text);
}

.limit-separator {
	color: var(--ql-text-muted);
	margin: 0 0.125rem;
}

.limit-unit {
	font-size: 0.875rem;
	font-weight: 400;
	color: var(--ql-text-muted);
	margin-left: 0.25rem;
}

.plan-badge {
	padding: 0.25rem 0.625rem;
	font-size: 0.75rem;
	font-weight: 500;
	border-radius: 9999px;
	text-transform: uppercase;
}

.badge-free {
	background: rgba(107, 114, 128, 0.1);
	color: #6b7280;
}

.badge-starter {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.badge-pro {
	background: rgba(139, 92, 246, 0.1);
	color: #8b5cf6;
}

.badge-enterprise {
	background: rgba(236, 72, 153, 0.1);
	color: #ec4899;
}

/* Limit Progress Bar */
.limit-bar {
	height: 0.375rem;
	background: var(--ql-border);
	border-radius: 9999px;
	overflow: hidden;
	margin-bottom: 0.5rem;
}

.limit-fill {
	height: 100%;
	background: var(--ql-accent);
	border-radius: 9999px;
	transition: width 0.3s ease;
}

.limit-fill.fill-warning {
	background: #eab308;
}

.limit-fill.fill-danger {
	background: #ef4444;
}

/* Limit Warning */
.limit-warning {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.75rem;
	background: rgba(239, 68, 68, 0.1);
	border-radius: 0.375rem;
	font-size: 0.75rem;
	color: #dc2626;
	margin-top: 0.5rem;
}

.warning-icon {
	width: 1rem;
	height: 1rem;
	flex-shrink: 0;
}

/* Credit pool info */
.credit-pool-info {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 0.5rem 0.75rem;
	background: var(--ql-accent-soft);
	border-radius: 0.375rem;
	margin-bottom: 0.5rem;
}

.pool-label {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.025em;
}

.pool-value {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
}

.pool-rate {
	font-size: 0.75rem;
	font-weight: 400;
	color: var(--ql-text-muted);
}

/* Purchased seats info */
.purchased-seats-info {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	padding: 0.5rem 0.75rem;
	background: rgba(139, 92, 246, 0.05);
	border-radius: 0.375rem;
	margin-bottom: 0.5rem;
}

.seat-cost {
	font-weight: 500;
	color: var(--ql-text);
	margin-left: 0.25rem;
}

/* Estimated monthly bill — anchors admins to the total spend (seats
   + GST when computable). Visually heavier than the per-seat notice
   because it answers the bigger question: "what am I paying total". */
.monthly-estimate {
	padding: 0.625rem 0.75rem;
	margin-bottom: 0.5rem;
	background: rgba(34, 197, 94, 0.06);
	border: 1px solid rgba(34, 197, 94, 0.2);
	border-radius: 0.5rem;
}

.estimate-row {
	display: flex;
	justify-content: space-between;
	align-items: baseline;
	gap: 0.5rem;
}

.estimate-label {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.025em;
}

.estimate-value {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
}

.estimate-suffix {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	margin-left: 0.25rem;
}

.estimate-breakdown {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.25rem;
}

/* Per-seat pricing notice — shown on per-user plans before the user
   exceeds min_users, so admins know what adding a seat will cost. */
.seat-pricing-notice {
	display: flex;
	align-items: flex-start;
	gap: 0.5rem;
	padding: 0.5rem 0.75rem;
	margin-bottom: 0.5rem;
	background: var(--ql-accent-soft);
	border: 1px solid var(--ql-accent-soft);
	border-radius: 0.375rem;
	font-size: 0.75rem;
	color: var(--ql-text);
	line-height: 1.4;
}

.seat-pricing-notice svg {
	width: 0.875rem;
	height: 0.875rem;
	flex-shrink: 0;
	margin-top: 0.125rem;
	color: var(--ql-accent);
}

.seat-pricing-notice strong {
	font-weight: 600;
}

/* Upgrade hint */
.upgrade-hint {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.hint-separator {
	margin: 0 0.5rem;
}
</style>
