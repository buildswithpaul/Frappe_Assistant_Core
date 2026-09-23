import { mount } from "@vue/test-utils";
import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import CreditMeter from "../CreditMeter.vue";
import { useUserStore } from "@/stores/userStore";

const TEAM_POOL = {
	plan: "Team",
	quota_total: 350000,
	quota_used: 180000,
	quota_remaining: 170000,
	percentage_used: 51.4,
	is_unlimited: false,
};

function capped({ limit = 20000, used = 12400 } = {}) {
	return {
		monthly_credit_limit: limit,
		credits_used_this_month: used,
		has_individual_limit: true,
		team_credit_quota: TEAM_POOL.quota_total,
		team_credits_used: TEAM_POOL.quota_used,
	};
}

function pooled() {
	return {
		monthly_credit_limit: 0,
		credits_used_this_month: 4200,
		has_individual_limit: false,
		team_credit_quota: TEAM_POOL.quota_total,
		team_credits_used: TEAM_POOL.quota_used,
	};
}

describe("CreditMeter scoping", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		store = useUserStore();
	});

	it("tracks the member's own cap when they have an individual limit", () => {
		store.quotaInfo = { ...TEAM_POOL };
		store.myCreditStatus = capped();

		const wrapper = mount(CreditMeter);

		// 12400 / 20000 — the member's own cap, not the team's 51%.
		expect(wrapper.find(".meter-label").text()).toBe("62% used");
	});

	it("tracks the team pool when the member has no individual limit", () => {
		store.quotaInfo = { ...TEAM_POOL };
		store.myCreditStatus = pooled();

		const wrapper = mount(CreditMeter);

		expect(wrapper.find(".meter-label").text()).toBe("51% used");
	});

	it("falls back to the team pool before personal status has loaded", () => {
		store.quotaInfo = { ...TEAM_POOL };
		store.myCreditStatus = null;

		const wrapper = mount(CreditMeter);

		expect(wrapper.find(".meter-label").text()).toBe("51% used");
	});

	it("renders a capped member's meter inside an unlimited team plan", () => {
		store.quotaInfo = { ...TEAM_POOL, quota_total: -1, is_unlimited: true, percentage_used: 0 };
		store.myCreditStatus = capped({ limit: 20000, used: 5000 });

		const wrapper = mount(CreditMeter);

		expect(wrapper.find(".credit-meter").exists()).toBe(true);
		expect(wrapper.find(".meter-label").text()).toBe("25% used");
	});

	it("hides entirely when neither a personal cap nor a team quota exists", () => {
		store.quotaInfo = { ...TEAM_POOL, quota_total: 0, percentage_used: 0 };
		store.myCreditStatus = pooled();

		const wrapper = mount(CreditMeter);

		expect(wrapper.find(".credit-meter").exists()).toBe(false);
	});

	it("names the scope in the tooltip so the number is never ambiguous", () => {
		store.quotaInfo = { ...TEAM_POOL };
		store.myCreditStatus = capped();

		const personal = mount(CreditMeter);
		expect(personal.find(".credit-meter").attributes("title")).toContain("Your limit");
		expect(personal.find(".credit-meter").attributes("title")).toContain("12.4k of 20.0k");

		store.myCreditStatus = pooled();
		const team = mount(CreditMeter);
		expect(team.find(".credit-meter").attributes("title")).toContain("Team plan");
		expect(team.find(".credit-meter").attributes("title")).toContain("180.0k of 350.0k");
	});
});

describe("CreditMeter live updates", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		store = useUserStore();
	});

	it("advances a capped member's meter by this turn's credits", async () => {
		store.quotaInfo = { ...TEAM_POOL };
		store.myCreditStatus = capped();

		const wrapper = mount(CreditMeter);
		store.applyQuotaFromStream({
			quota_used: 200000,
			quota_total: 350000,
			quota_remaining: 150000,
			credits_used: 600,
		});
		await wrapper.vm.$nextTick();

		// 13000 / 20000 — moved by the turn's cost, NOT replaced by the
		// tenant-wide 57% that rides on the same event.
		expect(wrapper.find(".meter-label").text()).toBe("65% used");
	});

	it("keeps the team meter live for pooled members", async () => {
		store.quotaInfo = { ...TEAM_POOL };
		store.myCreditStatus = pooled();

		const wrapper = mount(CreditMeter);
		store.applyQuotaFromStream({
			quota_used: 315000,
			quota_total: 350000,
			quota_remaining: 35000,
			credits_used: 600,
		});
		await wrapper.vm.$nextTick();

		expect(wrapper.find(".meter-label").text()).toBe("90% used");
	});

	it("warns in red once a capped member crosses the critical threshold", async () => {
		store.quotaInfo = { ...TEAM_POOL };
		store.myCreditStatus = capped({ limit: 20000, used: 17800 });

		const wrapper = mount(CreditMeter);
		store.applyQuotaFromStream({
			quota_used: 181000,
			quota_total: 350000,
			quota_remaining: 169000,
			credits_used: 400,
		});
		await wrapper.vm.$nextTick();

		expect(wrapper.find(".credit-meter").classes()).toContain("is-critical");
	});

	it("leaves the personal counter alone when the turn reports no cost", async () => {
		store.quotaInfo = { ...TEAM_POOL };
		store.myCreditStatus = capped();

		const wrapper = mount(CreditMeter);
		store.applyQuotaFromStream({ quota_used: 180000, quota_total: 350000 });
		await wrapper.vm.$nextTick();

		expect(wrapper.find(".meter-label").text()).toBe("62% used");
	});
});
