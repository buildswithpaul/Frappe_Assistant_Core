import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CreditMeter from "@/components/chat/CreditMeter.vue";
import { useUserStore } from "@/stores/userStore";
import MyCreditsBand from "./MyCreditsBand.vue";

const POOL = { quota_used: 2500, quota_total: 10000, billing_cycle_start: "2026-10-05" };

function seed({ quota = POOL, mine = null } = {}) {
	const store = useUserStore();
	store.quotaInfo = quota;
	store.myCreditStatus = mine;
}

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
		const text = mount(MyCreditsBand).text();
		for (const part of ["1,200", "2,000", "Your monthly limit", "Shared by your workspace"]) {
			expect(text).toContain(part);
		}
	});

	it("falls back to the shared pool when there is no personal limit", () => {
		seed();
		const text = mount(MyCreditsBand).text();
		for (const part of ["2,500", "10,000", "This month", "Shared by your workspace"]) {
			expect(text).toContain(part);
		}
		expect(text).not.toContain("Your monthly limit");
	});

	it("says what to do at the limit and offers no Buy button", () => {
		seed({ mine: personal(2000) });
		const wrapper = mount(MyCreditsBand);
		const notice = wrapper.get('[data-test="at-limit"]').text();
		expect(notice).toContain("Ask a workspace admin");
		expect(notice).toContain("resets on Nov 5, 2026");
		expect(wrapper.find('[data-test="buy-credits"]').exists()).toBe(false);
		expect(wrapper.text()).toContain("100%");
	});

	it("has no at-limit notice under the limit", () => {
		seed({ mine: personal(1999) });
		expect(mount(MyCreditsBand).find('[data-test="at-limit"]').exists()).toBe(false);
	});

	it("uses the same figures as the top-bar meter", () => {
		seed({ mine: personal(1200) });
		const meter = mount(CreditMeter);
		const band = mount(MyCreditsBand);
		expect(meter.attributes("title")).toContain("1.2k of 2.0k");
		expect(band.text()).toContain("1,200");
		expect(band.text()).toContain("2,000");
		expect(meter.text()).toContain("60% used");
		expect(band.text()).toContain("60% used");
	});
});
