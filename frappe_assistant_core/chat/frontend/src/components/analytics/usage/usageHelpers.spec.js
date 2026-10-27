import { describe, it, expect } from "vitest";
import { countMembersAtLimit, membersAtLimitLabel, monthAllowance } from "./usageHelpers";

describe("monthAllowance", () => {
	it("reads the billing cycle, not a window sum", () => {
		expect(
			monthAllowance({ quota_used: 2500, quota_total: 10000, percentage_used: 25, billing_cycle_start: "2026-10-05" }),
		).toEqual({ used: 2500, total: 10000, percent: 25, unlimited: false, unknown: false, resetDate: "Nov 5, 2026" });
	});

	it("flags an unlimited plan from a total of -1", () => {
		expect(monthAllowance({ quota_used: 5, quota_total: -1, percentage_used: 0 }).unlimited).toBe(true);
	});

	it("treats a missing percentage as 0, never NaN", () => {
		expect(monthAllowance({ quota_used: 0, quota_total: 100 }).percent).toBe(0);
	});

	it("caps the percentage at 100", () => {
		expect(monthAllowance({ quota_used: 12000, quota_total: 10000, percentage_used: 120 }).percent).toBe(100);
	});

	it("rounds down and keeps 99 until the allowance is spent", () => {
		expect(monthAllowance({ quota_used: 8760, quota_total: 10000 }).percent).toBe(87);
		expect(monthAllowance({ quota_used: 9960, quota_total: 10000 }).percent).toBe(99);
	});

	it("marks the fallback snapshot unknown, never unlimited", () => {
		const fallback = { plan: "Unknown", quota_used: 0, quota_total: -1, is_fallback: true, billing_cycle_start: "2026-10-05" };
		const result = monthAllowance(fallback);
		expect(result.unknown).toBe(true);
		expect(result.unlimited).toBe(false);
		expect(result.resetDate).toBeNull();
	});
});

describe("countMembersAtLimit", () => {
	it("counts only members who hit a personal limit", () => {
		expect(
			countMembersAtLimit([
				{ monthly_credit_limit: 100, credits_used_this_month: 100 },
				{ monthly_credit_limit: 0, credits_used_this_month: 999 },
				{ monthly_credit_limit: 100, credits_used_this_month: 10 },
			]),
		).toBe(1);
	});
});

describe("membersAtLimitLabel", () => {
	const atLimit = { monthly_credit_limit: 5, credits_used_this_month: 5 };
	it("is the plain count when the page is complete", () => {
		expect(membersAtLimitLabel({ users: [atLimit, atLimit], pagination: { has_more: false } })).toBe(2);
		expect(membersAtLimitLabel({ users: [], pagination: { has_more: false } })).toBe(0);
	});
	it("is a lower bound when more members exist than the page holds", () => {
		expect(membersAtLimitLabel({ users: [atLimit, atLimit, atLimit], pagination: { has_more: true } })).toBe("3+");
	});
	it("is hidden when the page has more behind it and none are at their limit", () => {
		expect(membersAtLimitLabel({ users: [{ monthly_credit_limit: 0 }], pagination: { has_more: true } })).toBeNull();
	});
});
