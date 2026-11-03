import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import CreditsBand from "./CreditsBand.vue";

const QUOTA = {
	quota_used: 2500,
	quota_total: 10000,
	percentage_used: 25,
	billing_cycle_start: "2026-10-05",
	credit_balance: 4000,
};

async function mountBand(props = {}) {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/settings/users", component: { template: "<div />" } }],
	});
	router.push("/");
	await router.isReady();
	return mount(CreditsBand, { props: { quota: QUOTA, ...props }, global: { plugins: [router] } });
}

describe("CreditsBand", () => {
	// The reset date rolls forward with the clock, so pin it.
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date(2026, 9, 27, 12));
	});
	afterEach(() => vi.useRealTimers());

	it("shows this month from the quota, not a window sum", async () => {
		const text = (await mountBand()).text();
		for (const part of ["2,500", "10,000", "25%", "Resets on Nov 5, 2026"]) expect(text).toContain(part);
	});

	it("shows prepaid credits and emits buy-credits", async () => {
		const wrapper = await mountBand();
		expect(wrapper.text()).toContain("4,000");
		await wrapper.get('[data-test="buy-credits"]').trigger("click");
		expect(wrapper.emitted("buy-credits")).toHaveLength(1);
	});

	it("says Unlimited plan and draws no bar", async () => {
		const wrapper = await mountBand({ quota: { ...QUOTA, quota_total: -1, is_unlimited: true } });
		expect(wrapper.text()).toContain("Unlimited plan");
		expect(wrapper.find(".allowance-bar").exists()).toBe(false);
	});

	it("rounds the share down and keeps 99 from reading as exhausted", async () => {
		const at = (used) => mountBand({ quota: { ...QUOTA, quota_used: used } });
		expect((await at(8760)).text()).toContain("87% used");
		const almost = await at(9960);
		expect(almost.text()).toContain("99% used");
		expect(almost.get(".allowance-bar").classes()).not.toContain("is-exhausted");
		expect((await at(10000)).text()).toContain("100% used");
	});

	it("rounds the credits to whole numbers", async () => {
		const wrapper = await mountBand({ quota: { ...QUOTA, quota_used: 31173.801, quota_total: 100000 } });
		expect(wrapper.text()).toContain("31,174");
		expect(wrapper.text()).not.toContain("31,173.801");
	});

	it("rolls a stale cycle start to the next reset after today", async () => {
		const wrapper = await mountBand({ quota: { ...QUOTA, billing_cycle_start: "2026-09-26" } });
		expect(wrapper.text()).toContain("Resets on Nov 26, 2026");
	});

	it("does not call the fallback snapshot an unlimited plan", async () => {
		const wrapper = await mountBand({
			quota: { plan: "Unknown", quota_used: 0, quota_total: -1, is_fallback: true, billing_cycle_start: "2026-10-05" },
		});
		const text = wrapper.text();
		expect(text).not.toContain("Unlimited");
		expect(text).toContain("Couldn't load this month's figures.");
		expect(text).not.toContain("Resets on");
		expect(text).not.toContain("% used");
		expect(wrapper.find(".allowance-bar").exists()).toBe(false);
	});

	it("shows an unknown extra-credit balance as a dash, never 0", async () => {
		// Boot's quotaInfo carries no credit_balance or billing_cycle_start.
		const { credit_balance, billing_cycle_start, ...boot } = QUOTA;
		const wrapper = await mountBand({ quota: boot });
		const extra = wrapper.get(".extra-card .card-value");
		expect(extra.text()).toBe("\u2014");
		expect(wrapper.find('[data-test="buy-credits"]').exists()).toBe(true);
		expect(wrapper.text()).not.toContain("Resets on");
	});

	it("uses the singular for one member and plural for a capped count", async () => {
		expect((await mountBand({ membersAtLimit: 1 })).text()).toContain("1 member at their limit");
		expect((await mountBand({ membersAtLimit: "3+" })).text()).toContain("3+ members at their limit");
	});

	it.each([
		[79, ""],
		[80, "is-warning"],
		[90, "is-critical"],
		[100, "is-exhausted"],
	])("tones the bar at %i%%", async (percent, tone) => {
		const wrapper = await mountBand({ quota: { ...QUOTA, quota_used: percent * 100 } });
		const bar = wrapper.get(".allowance-bar");
		expect(bar.classes().filter((c) => c.startsWith("is-"))).toEqual(tone ? [tone] : []);
	});

	it("links members at their limit to Users", async () => {
		const wrapper = await mountBand({ membersAtLimit: 2 });
		expect(wrapper.text()).toContain("2 members at their limit");
		expect(wrapper.get("a").attributes("href")).toMatch(/\/settings\/users$/);
		expect((await mountBand({ membersAtLimit: null })).find('[data-test="members-at-limit"]').exists()).toBe(false);
		expect((await mountBand({ membersAtLimit: 0 })).find('[data-test="members-at-limit"]').exists()).toBe(false);
	});
});
