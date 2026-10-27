import { describe, it, expect } from "vitest";
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
