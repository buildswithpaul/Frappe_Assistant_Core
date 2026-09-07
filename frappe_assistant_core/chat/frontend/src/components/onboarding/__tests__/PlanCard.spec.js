import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { vi } from "vitest";
import PlanCard from "@/components/onboarding/PlanCard.vue";
import { useUserStore } from "@/stores/userStore";

const { getQuotaStatus, getMyCreditStatus } = vi.hoisted(() => ({
	getQuotaStatus: vi.fn(),
	getMyCreditStatus: vi.fn(),
}));

vi.mock("@/api/client", () => ({
	api: {
		billing: { getQuotaStatus },
		users: { getMyCreditStatus },
	},
}));

const FREE_TENANT = { success: true, plan: "Free", quota_total: 500, quota_used: 0 };
const TEAM_PRO_TENANT = {
	success: true,
	plan: "Team Pro",
	quota_total: 450000,
	quota_used: 44757,
};
const NO_PERSONAL_CAP = { has_individual_limit: false, monthly_credit_limit: 0 };
const CAPPED_MEMBER = {
	has_individual_limit: true,
	monthly_credit_limit: 50000,
	credits_used_this_month: 3.84,
};

async function mountCard() {
	const wrapper = mount(PlanCard, { global: { stubs: { FacoRobot: true } } });
	await flushPromises();
	return wrapper;
}

const quotaText = (wrapper) => wrapper.find("[data-test=plan-quota]").text();

describe("PlanCard", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		getQuotaStatus.mockReset().mockResolvedValue(FREE_TENANT);
		getMyCreditStatus.mockReset().mockResolvedValue(NO_PERSONAL_CAP);
	});

	it("names the tenant's actual plan", async () => {
		getQuotaStatus.mockResolvedValue(TEAM_PRO_TENANT);
		const wrapper = await mountCard();
		expect(wrapper.text()).toContain("You're on the Team Pro plan");
	});

	it("shows the capped member their own limit, not the team pool", async () => {
		getQuotaStatus.mockResolvedValue(TEAM_PRO_TENANT);
		getMyCreditStatus.mockResolvedValue(CAPPED_MEMBER);
		const wrapper = await mountCard();
		expect(quotaText(wrapper)).toContain("50,000");
		expect(quotaText(wrapper)).not.toContain("450,000");
	});

	it("labels the quota as personal when a cap governs the member", async () => {
		getQuotaStatus.mockResolvedValue(TEAM_PRO_TENANT);
		getMyCreditStatus.mockResolvedValue(CAPPED_MEMBER);
		const wrapper = await mountCard();
		expect(quotaText(wrapper)).toMatch(/your limit/i);
	});

	it("shows the team pool when no cap governs the member", async () => {
		getQuotaStatus.mockResolvedValue(TEAM_PRO_TENANT);
		const wrapper = await mountCard();
		expect(quotaText(wrapper)).toContain("450,000");
		expect(quotaText(wrapper)).not.toMatch(/your limit/i);
	});

	it("keeps Free-plan framing for a free tenant", async () => {
		const wrapper = await mountCard();
		expect(wrapper.text()).toContain("You're on the Free plan");
		expect(wrapper.text()).toContain("No credit card required");
		expect(quotaText(wrapper)).toContain("500");
	});

	it("drops the no-credit-card line on a paid plan", async () => {
		getQuotaStatus.mockResolvedValue(TEAM_PRO_TENANT);
		const wrapper = await mountCard();
		expect(wrapper.text()).not.toContain("No credit card required");
	});

	it("says Unlimited rather than printing the -1 sentinel", async () => {
		getQuotaStatus.mockResolvedValue({ ...TEAM_PRO_TENANT, quota_total: -1 });
		const wrapper = await mountCard();
		expect(quotaText(wrapper)).toMatch(/unlimited/i);
		expect(quotaText(wrapper)).not.toContain("-1");
	});

	it("hides the quota rather than inventing a number when billing is unreachable", async () => {
		getQuotaStatus.mockRejectedValue(new Error("AR unreachable"));
		getMyCreditStatus.mockRejectedValue(new Error("AR unreachable"));
		const wrapper = await mountCard();
		expect(wrapper.find("[data-test=plan-quota]").exists()).toBe(false);
		expect(wrapper.find("[data-test=plan-continue]").exists()).toBe(true);
	});

	it("shows See plans to admins", async () => {
		useUserStore().isAdmin = true;
		const wrapper = await mountCard();
		expect(wrapper.find("[data-test=plan-see-plans]").exists()).toBe(true);
	});

	it("hides See plans for non-admins", async () => {
		useUserStore().isAdmin = false;
		const wrapper = await mountCard();
		expect(wrapper.find("[data-test=plan-see-plans]").exists()).toBe(false);
	});

	it("emits continue when the primary button is clicked", async () => {
		const wrapper = await mountCard();
		await wrapper.find("[data-test=plan-continue]").trigger("click");
		expect(wrapper.emitted("continue")).toBeTruthy();
	});
});
