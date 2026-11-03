import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

const QUOTA = {
	quota_used: 2500,
	quota_total: 10000,
	percentage_used: 25,
	billing_cycle_start: "2026-10-05",
	credit_balance: 4000,
};

vi.mock("@/api/client", () => ({
	api: {
		analytics: {
			getData: vi.fn(),
			getConversations: vi.fn(),
		},
		billing: {
			getQuotaStatus: vi.fn(),
			getAvailableGateways: vi.fn(),
		},
		users: { list: vi.fn() },
	},
}));

import { api } from "@/api/client";
import CreditPurchaseModal from "@/components/settings/CreditPurchaseModal.vue";
import { useUserStore } from "@/stores/userStore";
import WorkspaceUsage from "./WorkspaceUsage.vue";

const stubs = {
	DailyTrendChart: true,
	SourceBreakdown: true,
	UserBreakdown: true,
	ModelBreakdown: true,
	ConversationList: true,
	ConversationDrillDown: true,
	SummaryCards: true,
};

// The router of the page being mounted, for mocks that need to look at it mid-mount.
let currentRouter = null;

async function mountUsage(path = "/analytics") {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/analytics", component: { template: "<div />" } },
			{ path: "/settings/users", component: { template: "<div />" } },
		],
	});
	currentRouter = router;
	router.push(path);
	await router.isReady();
	const wrapper = mount(WorkspaceUsage, {
		props: { range: 30 },
		global: { plugins: [router], stubs },
	});
	await flushPromises();
	return { wrapper, router };
}

describe("WorkspaceUsage", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
		// Only admins reach this page; loadUser sets isAdmin from the server.
		useUserStore().isAdmin = true;
		api.analytics.getData.mockResolvedValue({ summary: {}, daily: [], by_user: [], by_model: [], by_source: [] });
		api.analytics.getConversations.mockResolvedValue({
			conversations: [],
			summary: {},
			pagination: { has_more: false },
		});
		api.billing.getQuotaStatus.mockResolvedValue(QUOTA);
		api.billing.getAvailableGateways.mockResolvedValue({ gateways: [{ name: "stripe", is_recommended: true }] });
		api.users.list.mockResolvedValue({
			users: [{ monthly_credit_limit: 5, credits_used_this_month: 5 }],
			pagination: { has_more: false },
		});
	});

	it("refreshes the quota on mount even when boot loaded one", async () => {
		// Boot's get_boot_payload seeds quotaInfo before any page mounts.
		const store = useUserStore();
		store.quotaInfo = { ...QUOTA, credit_balance: 1 };
		await mountUsage();
		expect(api.billing.getQuotaStatus).toHaveBeenCalledTimes(1);
	});

	it("opens the purchase modal in place from the band", async () => {
		const { wrapper, router } = await mountUsage();
		await wrapper.get('[data-test="buy-credits"]').trigger("click");
		await flushPromises();
		expect(wrapper.findComponent(CreditPurchaseModal).props("isOpen")).toBe(true);
		expect(router.currentRoute.value.path).toBe("/analytics");
	});

	it("strips buy before the purchase modal opens", async () => {
		let buyWhenOpening = "unset";
		api.billing.getAvailableGateways.mockImplementation(async () => {
			buyWhenOpening = currentRouter.currentRoute.value.query.buy;
			return { gateways: [{ name: "stripe", is_recommended: true }] };
		});
		const { wrapper, router } = await mountUsage("/analytics?buy=1");
		expect(buyWhenOpening).toBeUndefined();
		expect(router.currentRoute.value.query.buy).toBeUndefined();
		expect(wrapper.findComponent(CreditPurchaseModal).props("isOpen")).toBe(true);
	});

	it("counts members at their limit from one users call", async () => {
		const { wrapper } = await mountUsage();
		expect(api.users.list).toHaveBeenCalledTimes(1);
		expect(api.users.list).toHaveBeenCalledWith("Active", 100, 0);
		expect(wrapper.text()).toContain("1 member at their limit");
	});

	it("shows a lower bound when more members exist than one page holds", async () => {
		const atLimit = { monthly_credit_limit: 5, credits_used_this_month: 5 };
		api.users.list.mockResolvedValue({
			users: [atLimit, atLimit, atLimit, { monthly_credit_limit: 0 }],
			pagination: { has_more: true },
		});
		const { wrapper } = await mountUsage();
		expect(wrapper.text()).toContain("3+ members at their limit");
	});

	it("hides the tile when the page has more behind it and none are at their limit", async () => {
		api.users.list.mockResolvedValue({ users: [{ monthly_credit_limit: 0 }], pagination: { has_more: true } });
		const { wrapper } = await mountUsage();
		expect(wrapper.find('[data-test="members-at-limit"]').exists()).toBe(false);
	});

	it("leaves the tile out when the members call fails", async () => {
		api.users.list.mockRejectedValue(new Error("boom"));
		const { wrapper } = await mountUsage();
		expect(wrapper.find('[data-test="members-at-limit"]').exists()).toBe(false);
		expect(wrapper.find(".credits-band").exists()).toBe(true);
	});

	it("keeps the band, with Buy credits, when analytics fails", async () => {
		api.analytics.getData.mockResolvedValue({ error: "Analytics are down" });
		const { wrapper } = await mountUsage();
		expect(wrapper.text()).toContain("Analytics are down");
		expect(wrapper.find(".credits-band").exists()).toBe(true);
		expect(wrapper.find('[data-test="buy-credits"]').exists()).toBe(true);
	});

	it("does not unmount the band while a new range loads", async () => {
		const { wrapper } = await mountUsage();
		const band = wrapper.find(".credits-band").element;
		api.analytics.getData.mockReturnValue(new Promise(() => {}));
		await wrapper.setProps({ range: 7 });
		await flushPromises();
		expect(wrapper.find(".analytics-state").exists()).toBe(true);
		expect(wrapper.find(".credits-band").element).toBe(band);
	});

	it("shows an unknown extra-credit balance, not 0, when the refresh fails on boot data", async () => {
		// Boot seeds quotaInfo without credit_balance or billing_cycle_start.
		const { credit_balance, billing_cycle_start, ...boot } = QUOTA;
		useUserStore().quotaInfo = boot;
		api.billing.getQuotaStatus.mockRejectedValue(new Error("offline"));
		const { wrapper } = await mountUsage();
		expect(wrapper.get(".extra-card .card-value").text()).toBe("\u2014");
		expect(wrapper.text()).not.toContain("Resets on");
	});
});
