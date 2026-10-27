import { describe, it, expect } from "vitest";
import { countMembersAtLimit, monthAllowance } from "./usageHelpers";

describe("monthAllowance", () => {
	it("reads the billing cycle, not a window sum", () => {
		expect(
			monthAllowance({ quota_used: 2500, quota_total: 10000, percentage_used: 25, billing_cycle_start: "2026-10-05" }),
		).toEqual({ used: 2500, total: 10000, percent: 25, unlimited: false, resetDate: "Nov 5, 2026" });
	});

	it("flags an unlimited plan from a total of -1", () => {
		expect(monthAllowance({ quota_used: 5, quota_total: -1, percentage_used: 0 }).unlimited).toBe(true);
	});

	it("caps the percentage at 100", () => {
		expect(monthAllowance({ quota_used: 12000, quota_total: 10000, percentage_used: 120 }).percent).toBe(100);
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
