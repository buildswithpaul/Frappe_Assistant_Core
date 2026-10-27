import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
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

	it("uses the singular for one member and plural for a capped count", async () => {
		expect((await mountBand({ membersAtLimit: 1 })).text()).toContain("1 member at their limit");
		expect((await mountBand({ membersAtLimit: "100+" })).text()).toContain("100+ members at their limit");
	});

	it.each([
		[79, ""],
		[80, "is-warning"],
		[90, "is-critical"],
		[100, "is-exhausted"],
	])("tones the bar at %i%%", async (percent, tone) => {
		const wrapper = await mountBand({ quota: { ...QUOTA, percentage_used: percent } });
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
