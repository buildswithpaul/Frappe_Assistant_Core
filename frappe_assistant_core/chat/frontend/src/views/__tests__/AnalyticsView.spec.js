import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

vi.mock("@/api/client", () => ({
	api: {
		analytics: {
			getData: vi.fn(),
			getMyUsage: vi.fn(),
			getConversations: vi.fn(),
			getMessageCredits: vi.fn(),
		},
		billing: { getQuotaStatus: vi.fn(), getAvailableGateways: vi.fn() },
		users: { list: vi.fn(), getMyCreditStatus: vi.fn() },
	},
}));

import { api } from "@/api/client";
import { useUserStore } from "@/stores/userStore";
import CreditPurchaseModal from "@/components/settings/CreditPurchaseModal.vue";
import AnalyticsView from "../AnalyticsView.vue";

const EMPTY = { summary: {}, daily: [], by_source: [], by_model: [], by_user: [] };
const stubs = {
	NavigationSidebar: true,
	DailyTrendChart: true,
	SourceBreakdown: true,
	UserBreakdown: true,
	ModelBreakdown: true,
	ConversationList: true,
	CreditPurchaseModal: true,
};

async function mountAt(path, { isAdmin }) {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/analytics", component: AnalyticsView }],
	});
	router.push(path);
	await router.isReady();
	useUserStore().isAdmin = isAdmin;
	const wrapper = mount(AnalyticsView, { global: { plugins: [router], stubs } });
	await flushPromises();
	return { wrapper, router };
}

describe("AnalyticsView", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
		api.analytics.getData.mockResolvedValue({ ...EMPTY, is_admin: true });
		api.analytics.getMyUsage.mockResolvedValue(EMPTY);
		api.analytics.getConversations.mockResolvedValue({ conversations: [], summary: {}, pagination: {} });
		api.users.list.mockResolvedValue({ users: [], pagination: {} });
		api.users.getMyCreditStatus.mockResolvedValue({ has_individual_limit: false });
	});

	// /analytics has no requireAdmin, so a member reaches it; isAdmin is what the real store
	// reports for a non-admin session user, and the query is whatever a pasted link carries.
	it("a member never calls workspace endpoints", async () => {
		const { wrapper } = await mountAt("/analytics?view=workspace&buy=1", { isAdmin: false });
		expect(api.analytics.getMyUsage).toHaveBeenCalled();
		expect(api.analytics.getData).not.toHaveBeenCalled();
		expect(api.analytics.getConversations).not.toHaveBeenCalled();
		expect(api.users.list).not.toHaveBeenCalled();
		expect(wrapper.find(".usage-view-switch").exists()).toBe(false);
	});

	it("an admin switches to Mine and back", async () => {
		const { wrapper, router } = await mountAt("/analytics", { isAdmin: true });
		expect(wrapper.find(".usage-view-switch").exists()).toBe(true);
		expect(api.analytics.getMyUsage).not.toHaveBeenCalled();

		const button = (name) => wrapper.findAll(".usage-view-switch button").find((b) => b.text() === name);
		expect(button("Workspace").attributes("aria-pressed")).toBe("true");
		expect(button("Mine").attributes("aria-pressed")).toBe("false");
		await button("Mine").trigger("click");
		await flushPromises();
		expect(router.currentRoute.value.query.view).toBe("me");
		expect(api.analytics.getMyUsage).toHaveBeenCalled();
		expect(button("Mine").attributes("aria-pressed")).toBe("true");
		expect(button("Workspace").attributes("aria-pressed")).toBe("false");
		expect(wrapper.find(".workspace-usage").exists()).toBe(false);
		api.analytics.getData.mockClear();

		await button("Workspace").trigger("click");
		await flushPromises();
		expect(router.currentRoute.value.query.view).toBeUndefined();
		expect(api.analytics.getData).toHaveBeenCalled();
		expect(wrapper.find(".workspace-usage").exists()).toBe(true);
	});

	it("does not carry a purchase link into the workspace view", async () => {
		const { wrapper, router } = await mountAt("/analytics?view=me&buy=1", { isAdmin: true });
		const workspace = wrapper.findAll(".usage-view-switch button").find((b) => b.text() === "Workspace");
		await workspace.trigger("click");
		await flushPromises();
		expect(router.currentRoute.value.query.buy).toBeUndefined();
		expect(wrapper.findComponent(CreditPurchaseModal).props("isOpen")).toBe(false);
	});
});
