import { describe, it, expect } from "vitest";

import { formatCurrency, getPlanPriceMeta, getSeatSummary } from "./billingFormatters";

describe("billingFormatters.formatCurrency", () => {
	it("renders INR amounts with the rupee symbol, not USD", () => {
		const out = formatCurrency(2999, "INR");
		expect(out).toContain("₹");
		expect(out).not.toContain("$");
	});

	it("honors USD when that is the invoice currency", () => {
		expect(formatCurrency(49, "USD")).toContain("$");
	});

	it("falls back to USD when no currency is supplied", () => {
		expect(formatCurrency(49)).toContain("$");
		expect(formatCurrency(49, "")).toContain("$");
	});
});

const perUserPlan = (overrides = {}) => ({
	id: "team-basic",
	name: "Team Basic",
	pricing: {
		currency: "INR",
		currency_symbol: "₹",
		gateway: "razorpay",
		monthly: 5997,
		annual: 59997,
		per_seat_monthly: 1999,
		per_seat_annual: 19999,
		is_per_user: true,
		min_users: 3,
		...overrides,
	},
});

const flatPlan = () => ({
	id: "basic",
	name: "Basic",
	pricing: {
		currency: "INR",
		currency_symbol: "₹",
		gateway: "razorpay",
		monthly: 1999,
		annual: 19999,
		is_per_user: false,
		min_users: null,
	},
});

describe("getPlanPriceMeta", () => {
	it("quotes a per-user plan by the seat, not the bundle", () => {
		const meta = getPlanPriceMeta(perUserPlan(), "monthly");

		// The headline is the seat price — Team Basic reads as ₹1,999 like
		// Basic, instead of ₹5,997 and apparently three times the price.
		expect(meta.kind).toBe("amount");
		expect(meta.amount).toBe(1999);
		expect(meta.period).toBe("/user/month");
		expect(meta.isPerUser).toBe(true);
		expect(meta.minUsers).toBe(3);
		expect(meta.minimumTotal).toBe(5997);
	});

	it("switches the seat price and period on the annual cycle", () => {
		const meta = getPlanPriceMeta(perUserPlan(), "annual");

		expect(meta.amount).toBe(19999);
		expect(meta.period).toBe("/user/year");
		expect(meta.minimumTotal).toBe(59997);
	});

	it("leaves a flat plan quoting its own price", () => {
		const meta = getPlanPriceMeta(flatPlan(), "monthly");

		expect(meta.amount).toBe(1999);
		expect(meta.period).toBe("/month");
		expect(meta.isPerUser).toBe(false);
		expect(meta.minimumTotal).toBeNull();
	});

	it("stays unavailable when the seat price is unset", () => {
		const meta = getPlanPriceMeta(
			perUserPlan({ monthly: null, per_seat_monthly: null }),
			"monthly",
		);

		expect(meta.kind).toBe("unavailable");
	});
});

describe("getSeatSummary", () => {
	const perUser = () => getPlanPriceMeta(perUserPlan(), "monthly");

	it("quotes the entry price when the plan is not the current one", () => {
		expect(getSeatSummary(perUser(), null, false)).toEqual({
			kind: "minimum",
			seats: 3,
			total: 5997,
		});
	});

	it("bills the seats the tenant pays for, not the members it has", () => {
		// The production case: 9 paid, 5 assigned. The card said "5 seats".
		expect(
			getSeatSummary(perUser(), { paid_seats: 9, assigned_seats: 5 }, true),
		).toEqual({ kind: "active", seats: 9, total: 17991 });
	});

	it("still quotes the minimum when the paid count sits below it", () => {
		expect(
			getSeatSummary(perUser(), { paid_seats: 3, assigned_seats: 1 }, true),
		).toEqual({ kind: "active", seats: 3, total: 5997 });
	});

	it("falls back to the minimum line when seat data is unavailable", () => {
		// Non-admins cannot read get_user_limit_status; the card must still
		// render something truthful rather than a seat count of zero.
		expect(getSeatSummary(perUser(), null, true)).toEqual({
			kind: "minimum",
			seats: 3,
			total: 5997,
		});
	});

	it("has nothing to say about a flat plan", () => {
		expect(
			getSeatSummary(getPlanPriceMeta(flatPlan(), "monthly"), null, true),
		).toBeNull();
	});
});
