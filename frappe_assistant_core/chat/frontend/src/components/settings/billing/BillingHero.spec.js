import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

import BillingHero from "./BillingHero.vue";

const RouterLink = {
	props: ["to"],
	template: "<a :href=\"to\"><slot /></a>",
};

const quota = {
	quota_used: 400,
	quota_total: 1000,
	percentage_used: 40,
	billing_cycle_start: "2026-10-05",
};

function mountHero(props = {}) {
	return mount(BillingHero, {
		props: { currentPlan: "Pro", quota, ...props },
		global: { stubs: { RouterLink } },
	});
}

describe("BillingHero", () => {
	// The reset date rolls forward with the clock, so pin it.
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date(2026, 9, 27, 12));
	});
	afterEach(() => vi.useRealTimers());

	it("states the share used rounded down, 99 until the allowance is spent", () => {
		const label = (q) => mountHero({ quota: { ...quota, ...q } }).find(".ring-percent").text();
		expect(label({ quota_used: 876, percentage_used: 87.6 })).toBe("87%");
		expect(label({ quota_used: 996, percentage_used: 99.6 })).toBe("99%");
		expect(label({ quota_used: 1000, percentage_used: 100 })).toBe("100%");
	});

	it("links quietly to the usage page", () => {
		const link = mountHero().find('a[data-test="see-usage"]');
		expect(link.exists()).toBe(true);
		expect(link.attributes("href")).toMatch(/\/analytics$/);
		expect(link.text()).toBe("See usage");
	});

	it("shows the same reset date as the usage page", () => {
		const w = mountHero({ usageResetDate: "Nov 30, 2026" });
		expect(w.find(".usage-reset").text()).toContain("Nov 5, 2026");
	});

	it("falls back to the dashboard reset date when the cycle start is unknown", () => {
		const w = mountHero({ quota: { ...quota, billing_cycle_start: null }, usageResetDate: "Nov 30, 2026" });
		expect(w.find(".usage-reset").text()).toContain("Nov 30, 2026");
	});
});
