import { describe, expect, it } from "vitest";
import { percentOf, percentUsed } from "./creditPercent";

describe("percentOf", () => {
	it("rounds down", () => expect(percentOf(876, 1000)).toBe(87));
	it("stays at 99 until the allowance is spent", () => expect(percentOf(996, 1000)).toBe(99));
	it("is 100 once used reaches total", () => {
		expect(percentOf(1000, 1000)).toBe(100);
		expect(percentOf(1200, 1000)).toBe(100);
	});
	it("is 0 without an allowance", () => {
		expect(percentOf(5, 0)).toBe(0);
		expect(percentOf(5, -1)).toBe(0);
	});
});

describe("percentUsed", () => {
	it("prefers used and total", () => {
		expect(percentUsed({ quota_used: 876, quota_total: 1000, percentage_used: 50 })).toBe(87);
	});
	it("falls back to percentage_used with the same rounding", () => {
		expect(percentUsed({ percentage_used: 87.6 })).toBe(87);
		expect(percentUsed({ percentage_used: 99.6 })).toBe(99);
		expect(percentUsed({ percentage_used: 100 })).toBe(100);
		expect(percentUsed({})).toBe(0);
	});
});
