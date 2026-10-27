import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
	api: {
		analytics: {
			getData: vi.fn(),
			getConversations: vi.fn(),
			getMessageCredits: vi.fn(),
		},
		billing: { getQuotaStatus: vi.fn(), getAvailableGateways: vi.fn() },
		users: { list: vi.fn() },
	},
}));

import { api } from "@/api/client";
import { useUserStore } from "@/stores/userStore";
import AnalyticsView from "./AnalyticsView.vue";

const stubs = {
	NavigationSidebar: true,
	WorkspaceUsage: { template: '<div data-test="workspace-usage" />' },
};

function mountView() {
	return mount(AnalyticsView, {
		global: { stubs, mocks: { $router: { push: vi.fn() } } },
	});
}

describe("AnalyticsView access", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
	});

	// /analytics no longer has requireAdmin, so a member reaches this view in production;
	// userStore.isAdmin is what the real store reports for a non-admin session user.
	it("renders no workspace usage and makes no workspace calls for a member", async () => {
		useUserStore().isAdmin = false;
		const wrapper = mountView();
		await flushPromises();
		expect(wrapper.find('[data-test="workspace-usage"]').exists()).toBe(false);
		expect(api.analytics.getData).not.toHaveBeenCalled();
		expect(api.analytics.getConversations).not.toHaveBeenCalled();
	});

	it("renders workspace usage for an admin", async () => {
		useUserStore().isAdmin = true;
		const wrapper = mountView();
		await flushPromises();
		expect(wrapper.find('[data-test="workspace-usage"]').exists()).toBe(true);
	});
});
