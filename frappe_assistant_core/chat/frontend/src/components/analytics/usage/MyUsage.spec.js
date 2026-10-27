import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
	api: {
		analytics: { getMyUsage: vi.fn() },
		billing: { getQuotaStatus: vi.fn() },
		users: { getMyCreditStatus: vi.fn() },
	},
}));

import { api } from "@/api/client";
import { useUserStore } from "@/stores/userStore";
import { testRouter } from "@/test-utils/router";
import MyUsage from "./MyUsage.vue";

const QUOTA = { quota_used: 2500, quota_total: 10000, billing_cycle_start: "2026-10-05", credit_balance: 0 };
const EMPTY = { summary: {}, daily: [], by_source: [], by_model: [] };

function day(n, credits, requests) {
	return { date: `2026-10-${String(n).padStart(2, "0")}`, credits_consumed: credits, request_count: requests };
}

// jsdom has no canvas, so a populated chart needs a stub; the empty state renders without one.
async function mountUsage({ stubs = {} } = {}) {
	const wrapper = mount(MyUsage, { global: { plugins: [testRouter()], stubs } });
	await flushPromises();
	return wrapper;
}

describe("MyUsage", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
		const store = useUserStore();
		store.quotaInfo = QUOTA;
		store.myCreditStatus = null;
		api.billing.getQuotaStatus.mockResolvedValue(QUOTA);
		api.users.getMyCreditStatus.mockResolvedValue({ has_individual_limit: false });
	});

	it("keeps the credits band and offers Retry when the usage call fails", async () => {
		api.analytics.getMyUsage.mockRejectedValueOnce(new Error("AR is unreachable"));
		const wrapper = await mountUsage();
		expect(wrapper.text()).toContain("AR is unreachable");
		expect(wrapper.text()).toContain("This month");
		expect(wrapper.find(".my-credits-band").exists()).toBe(true);

		api.analytics.getMyUsage.mockResolvedValueOnce(EMPTY);
		const retry = wrapper.findAll("button").find((b) => b.text() === "Retry");
		await retry.trigger("click");
		await flushPromises();
		expect(api.analytics.getMyUsage).toHaveBeenCalledTimes(2);
		expect(wrapper.text()).not.toContain("AR is unreachable");
		expect(wrapper.find(".my-credits-band").exists()).toBe(true);
	});

	it("renders an empty month without crashing", async () => {
		api.analytics.getMyUsage.mockResolvedValue(EMPTY);
		const wrapper = await mountUsage();
		expect(wrapper.text()).toContain("No daily usage data available");
		expect(wrapper.text()).toContain("No source data available");
		expect(wrapper.find(".retry-btn").exists()).toBe(false);
	});

	it("shows the trend against the earlier half of the range, as the workspace view does", async () => {
		// Prior half 100 credits a day, recent half 200: up 100%.
		const daily = [day(1, 100, 10), day(2, 100, 10), day(3, 200, 20), day(4, 200, 20)];
		api.analytics.getMyUsage.mockResolvedValue({ ...EMPTY, daily });
		const wrapper = await mountUsage({ stubs: { DailyTrendChart: true, SourceBreakdown: true } });
		expect(wrapper.findAll(".summary-card .trend-badge")).toHaveLength(2);
	});
});
