// Pure formatters for the Billing tab. Extracted out of useBillingData so
// they can be exercised without instantiating the composable.

import { formatCurrency as _formatCurrency } from "@/composables/useFormatters";

export function formatCurrency(amount, currency = "USD") {
	// Honor the invoice's own currency (INR for Razorpay, etc.); fall back
	// to USD only when the caller has none.
	return _formatCurrency(amount, currency || "USD");
}

export function formatInvoiceDate(invoice) {
	const timestamp = invoice.created_at || invoice.date;
	if (!timestamp) return "--";
	const date = typeof timestamp === "number" ? new Date(timestamp * 1000) : new Date(timestamp);
	return date.toLocaleDateString("en-US", {
		month: "short",
		day: "numeric",
		year: "numeric",
	});
}

export function formatStatus(status) {
	const statuses = {
		paid: "Paid",
		pending: "Pending",
		failed: "Failed",
		refunded: "Refunded",
		active: "Active",
	};
	return statuses[status] || status;
}

/**
 * Inspect a plan's pricing block and return a render-ready meta object.
 * Returned shape varies by `kind`:
 *   - "free"        → { kind }
 *   - "custom"      → { kind } (Enterprise — Contact Sales)
 *   - "unavailable" → { kind, reason, currency, gateway }
 *   - "amount"      → { kind, symbol, amount, formatted, period, currency, gateway }
 */
export function getPlanPriceMeta(plan, billingCycle) {
	const id = (plan.id || plan.name || "").toLowerCase();
	if (id === "free") return { kind: "free" };
	if (id === "enterprise") return { kind: "custom" };

	const pricing = plan.pricing || {};
	const symbol = pricing.currency_symbol || "$";
	const currency = pricing.currency || "USD";
	const gateway = pricing.gateway || "razorpay";
	const annual = billingCycle === "annual";
	const total = annual ? pricing.annual : pricing.monthly;

	// A per-user plan quotes the seat, not the bundle. `total` is already
	// per_seat × min_users, so leading with it put Team Basic's ₹5,997 beside
	// Basic's ₹1,999 and read as three times the price for the same thing.
	// The seat figure comes from the server rather than `total / min_users`,
	// so the card cannot round its way off the amount checkout charges.
	const isPerUser = Boolean(pricing.is_per_user);
	const perSeat = annual ? pricing.per_seat_annual : pricing.per_seat_monthly;
	const amount = isPerUser ? perSeat : total;

	if (amount == null) {
		return {
			kind: "unavailable",
			reason: pricing.unavailable_reason || `Pricing not configured for ${currency}.`,
			currency,
			gateway,
		};
	}

	return {
		kind: "amount",
		symbol,
		amount,
		formatted: `${symbol}${Number(amount).toLocaleString()}`,
		period: `${isPerUser ? "/user" : ""}${annual ? "/year" : "/month"}`,
		currency,
		gateway,
		isPerUser,
		minUsers: isPerUser ? pricing.min_users || 1 : null,
		/** What the seat minimum costs — the entry price for a team not on it yet. */
		minimumTotal: isPerUser ? total ?? null : null,
	};
}

/**
 * The line under a per-user plan's price: who is billed, and for how much.
 *
 * Mirrors `resolve_plan_price`, which charges `per_seat × max(user_count,
 * min_users)`. That floor-adjusted figure arrives as `paid_seats`, so this
 * no longer has to reason about the minimum itself — and it no longer reads
 * `active_users`, which counts member rows and had the card advertising
 * "5 seats" beside a bill for nine.
 *
 * `seatStatus` is null whenever the count is unknown: `get_user_limit_status`
 * is System Manager only, so a member viewing the Plans tab gets the entry
 * price instead of a wrong number.
 *
 * Returns null for flat plans, which have nothing seat-shaped to say.
 */
export function getSeatSummary(priceMeta, seatStatus, isCurrent) {
	if (!priceMeta?.isPerUser || priceMeta.kind !== "amount") return null;

	const minUsers = priceMeta.minUsers || 1;
	const perSeat = priceMeta.amount;
	const paid = seatStatus?.paid_seats;

	if (!isCurrent || paid == null) {
		return { kind: "minimum", seats: minUsers, total: priceMeta.minimumTotal };
	}

	return { kind: "active", seats: paid, total: perSeat * paid };
}

export function getPlanPrice(plan, billingCycle) {
	const meta = getPlanPriceMeta(plan, billingCycle);
	if (meta.kind === "free") return "Free";
	if (meta.kind === "custom") return "Custom";
	if (meta.kind === "unavailable") return "--";
	return meta.formatted;
}

/**
 * Decide what the action button should say for a plan card. Pure: takes
 * everything the composable knows about scheduled changes + upgrade
 * progress as inputs.
 */
export function getPlanActionText(plan, ctx) {
	const {
		upgrading,
		hasScheduledChange,
		scheduledChange,
		currentPlan,
		cancelAtPeriodEnd,
	} = ctx;
	const planId = (plan.id || plan.name || "").toLowerCase();
	if (plan.action === "current") return "Current Plan";
	if (planId === "enterprise") return "Contact Sales";
	if (upgrading) return "Processing...";

	// Pending cancellation: CTAs stay visible but inactive — Keep my plan
	// on the banner is the only path back to changing plans.
	const scheduledPlan = (scheduledChange?.new_plan || "").toLowerCase();
	if (cancelAtPeriodEnd && (!scheduledPlan || scheduledPlan === "free")) {
		if (planId === (currentPlan || "").toLowerCase()) return "Current Plan";
		return "Unavailable";
	}

	if (hasScheduledChange) {
		if (planId === currentPlan.toLowerCase()) return "Keep This Plan";
		if (planId === scheduledPlan) return "Scheduled";
	}

	if (plan.action === "upgrade") return "Upgrade";
	if (plan.action === "downgrade") return "Downgrade";

	const planOrder = [
		"free",
		"individual",
		"starter",
		"team",
		"pro",
		"organization",
		"enterprise",
	];
	const targetIdx = planOrder.indexOf(planId);
	const currentIdx = planOrder.indexOf(currentPlan.toLowerCase());
	if (targetIdx > currentIdx) return "Upgrade";
	if (targetIdx < currentIdx) return "Downgrade";
	return "Current Plan";
}
