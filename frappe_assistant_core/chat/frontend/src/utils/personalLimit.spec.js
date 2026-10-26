import { describe, expect, it } from "vitest";
import { personalLimitBlock } from "./personalLimit";

describe("personalLimitBlock", () => {
	it("is set when a member has used their whole personal limit", () => {
		expect(personalLimitBlock({ has_individual_limit: true, monthly_credit_limit: 10000, credits_used_this_month: 11234 })).toEqual({
			used: 11234,
			limit: 10000,
		});
		expect(personalLimitBlock({ monthly_credit_limit: "500", credits_used_this_month: "500" })).toEqual({ used: 500, limit: 500 });
	});

	it("is null under the limit, with no limit (0 draws on the team pool), or with no status", () => {
		expect(personalLimitBlock({ has_individual_limit: true, monthly_credit_limit: 10000, credits_used_this_month: 9999 })).toBe(null);
		expect(personalLimitBlock({ has_individual_limit: true, monthly_credit_limit: 0, credits_used_this_month: 50 })).toBe(null);
		expect(personalLimitBlock({ has_individual_limit: false, monthly_credit_limit: 100, credits_used_this_month: 500 })).toBe(null);
		expect(personalLimitBlock(null)).toBe(null);
	});
});
