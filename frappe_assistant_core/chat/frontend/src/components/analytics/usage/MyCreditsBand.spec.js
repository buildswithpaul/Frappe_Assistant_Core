import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CreditMeter from "@/components/chat/CreditMeter.vue";
import { useUserStore } from "@/stores/userStore";
import { testRouter } from "@/test-utils/router";
import MyCreditsBand from "./MyCreditsBand.vue";

const POOL = { quota_used: 2500, quota_total: 10000, billing_cycle_start: "2026-10-05" };

function seed({ quota = POOL, mine = null, isAdmin = false } = {}) {
	const store = useUserStore();
	store.isAdmin = isAdmin;
	store.quotaInfo = quota;
	store.myCreditStatus = mine;
}

const withRouter = () => ({ global: { plugins: [testRouter()] } });

const personal = (used) => ({
	has_individual_limit: true,
	monthly_credit_limit: 2000,
	credits_used_this_month: used,
});

describe("MyCreditsBand", () => {
	// The reset date rolls forward with the clock, so pin it.
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.useFakeTimers();
		vi.setSystemTime(new Date(2026, 9, 27, 12));
	});
	afterEach(() => vi.useRealTimers());

	it("shows the personal limit when the admin set one", () => {
		seed({ mine: personal(1200) });
		const text = mount(MyCreditsBand, withRouter()).text();
		for (const part of ["1,200", "2,000", "Your monthly limit"]) expect(text).toContain(part);
		expect(text).not.toContain("Shared by your workspace");
	});

	it("falls back to the shared pool when there is no personal limit", () => {
		seed();
		const text = mount(MyCreditsBand, withRouter()).text();
		for (const part of ["2,500", "10,000", "This month", "Shared by your workspace"]) {
			expect(text).toContain(part);
		}
		expect(text).not.toContain("Your monthly limit");
	});

	it("says what to do at the limit and offers no Buy button", () => {
		seed({ mine: personal(2000) });
		const wrapper = mount(MyCreditsBand, withRouter());
		const notice = wrapper.get('[data-test="at-limit"]').text();
		expect(notice).toContain("Ask a workspace admin");
		expect(notice).toContain("resets on Nov 5, 2026");
		expect(wrapper.find('[data-test="buy-credits"]').exists()).toBe(false);
		expect(wrapper.text()).toContain("100%");
	});

	it("has no at-limit notice under the limit", () => {
		seed({ mine: personal(1999) });
		expect(mount(MyCreditsBand, withRouter()).find('[data-test="at-limit"]').exists()).toBe(false);
	});

	it("uses the same figures as the top-bar meter", () => {
		seed({ mine: personal(1200) });
		const meter = mount(CreditMeter, withRouter());
		const band = mount(MyCreditsBand, withRouter());
		expect(meter.attributes("title")).toContain("1.2k of 2.0k");
		expect(band.text()).toContain("1,200");
		expect(band.text()).toContain("2,000");
		expect(meter.text()).toContain("60% used");
		expect(band.text()).toContain("60% used");
	});

	it("agrees with the meter on the shared pool too", () => {
		seed();
		const meter = mount(CreditMeter, withRouter());
		const band = mount(MyCreditsBand, withRouter());
		expect(meter.text()).toContain("25% used");
		expect(band.text()).toContain("25% used");
	});

	it("tells a member to ask an admin at their own limit", () => {
		seed({ mine: personal(2000) });
		const wrapper = mount(MyCreditsBand, withRouter());
		expect(wrapper.get('[data-test="at-limit"]').text()).toContain("Ask a workspace admin to raise it.");
		expect(wrapper.find('[data-test="change-limit"]').exists()).toBe(false);
	});

	it("points an admin at the Users settings at their own limit", () => {
		seed({ mine: personal(2000), isAdmin: true });
		const wrapper = mount(MyCreditsBand, withRouter());
		const notice = wrapper.get('[data-test="at-limit"]');
		expect(notice.text()).toContain("resets on Nov 5, 2026");
		expect(notice.text()).not.toContain("Ask a workspace admin");
		const link = wrapper.get('[data-test="change-limit"]');
		expect(link.text()).toBe("You can change it under Settings, Users.");
		expect(link.attributes("href")).toBe("/settings/users");
	});

	describe("workspace out of credits", () => {
		const spent = { ...POOL, quota_used: 10000 };

		it("says so when the shared pool is spent and no extra credits remain", () => {
			seed({ quota: { ...spent, credit_balance: 0 } });
			const text = mount(MyCreditsBand, withRouter()).get('[data-test="workspace-out"]').text();
			expect(text).toContain("Your workspace has used this month's credits.");
			expect(text).toContain("They reset on Nov 5, 2026.");
			expect(text).toContain("Ask a workspace admin to add more.");
		});

		it("offers an admin the purchase instead of telling them to ask an admin", () => {
			seed({ quota: { ...spent, credit_balance: 0 }, isAdmin: true });
			const w = mount(MyCreditsBand, withRouter());
			const notice = w.get('[data-test="workspace-out"]');
			expect(notice.text()).not.toContain("Ask a workspace admin");
			expect(w.get('[data-test="buy-more"]').attributes("href")).toContain("/analytics?buy=1");
		});

		it("stays quiet while extra credits remain", () => {
			seed({ quota: { ...spent, credit_balance: 500 } });
			expect(mount(MyCreditsBand, withRouter()).find('[data-test="workspace-out"]').exists()).toBe(false);
		});

		it("stays quiet under the pool limit", () => {
			seed({ quota: { ...POOL, credit_balance: 0 } });
			expect(mount(MyCreditsBand, withRouter()).find('[data-test="workspace-out"]').exists()).toBe(false);
		});

		it("is not shown for a member on their own limit", () => {
			seed({ quota: { ...spent, credit_balance: 0 }, mine: personal(100) });
			expect(mount(MyCreditsBand, withRouter()).find('[data-test="workspace-out"]').exists()).toBe(false);
		});

		it("is not shown on an unlimited plan", () => {
			seed({ quota: { ...spent, quota_total: -1, is_unlimited: true, credit_balance: 0 } });
			expect(mount(MyCreditsBand, withRouter()).find('[data-test="workspace-out"]').exists()).toBe(false);
		});
	});
});
