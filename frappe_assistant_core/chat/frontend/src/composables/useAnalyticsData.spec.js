import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
	api: {
		analytics: {
			getData: vi.fn(),
			getMyUsage: vi.fn(),
			getConversations: vi.fn(),
			getMessageCredits: vi.fn(),
		},
	},
}));

import { api } from "@/api/client";
import { useAnalyticsData } from "./useAnalyticsData";

describe("useAnalyticsData scope", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		api.analytics.getData.mockResolvedValue({ summary: {}, is_admin: true });
		api.analytics.getMyUsage.mockResolvedValue({ summary: { request_count: 3 }, daily: [] });
	});

	it("defaults to the workspace scope", async () => {
		await useAnalyticsData().loadData(7);
		expect(api.analytics.getData).toHaveBeenCalledWith(7);
		expect(api.analytics.getMyUsage).not.toHaveBeenCalled();
	});

	it("fetches only the member's own usage in the me scope", async () => {
		const usage = useAnalyticsData({ scope: "me" });
		await usage.loadData(7);
		expect(api.analytics.getMyUsage).toHaveBeenCalledWith(7);
		expect(api.analytics.getData).not.toHaveBeenCalled();
		expect(usage.summary.value.request_count).toBe(3);
	});

	it("skips workspace-only conversation calls in the me scope", async () => {
		const usage = useAnalyticsData({ scope: "me" });
		await usage.loadConversations();
		usage.loadMoreConversations();
		await usage.loadMessageCredits("c1");
		expect(api.analytics.getConversations).not.toHaveBeenCalled();
		expect(api.analytics.getMessageCredits).not.toHaveBeenCalled();
	});
});
