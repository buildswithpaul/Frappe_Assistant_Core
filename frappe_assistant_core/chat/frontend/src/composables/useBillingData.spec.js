import { describe, it, expect, vi, beforeEach } from "vitest";

const userStore = {
	isAdmin: true,
	quotaInfo: { plan: "Team" },
	outstanding: null,
	loadQuota: vi.fn(),
};

vi.mock("@/stores/userStore", () => ({ useUserStore: () => userStore }));
vi.mock("@/api/client", () => ({
	api: {
		billing: {
			getPageData: vi.fn(),
			getBillingDetails: vi.fn(),
		},
	},
}));

import { api } from "@/api/client";
import { useBillingData } from "@/composables/useBillingData.js";

const FAILURE = {
	reason: "Card declined by issuer.",
	failed_at: "2026-10-05 09:00:00",
	invoice: "AR-INV-1",
	dunning_level: "Warning",
	attempt: 1,
	total_attempts: 4,
	next_retry_on: "2026-10-06",
	past_due: false,
};

describe("useBillingData payment failure", () => {
	beforeEach(() => {
		userStore.loadQuota.mockReset().mockResolvedValue(undefined);
		api.billing.getBillingDetails.mockReset().mockResolvedValue(null);
		api.billing.getPageData.mockReset();
	});

	it("exposes the block AR sends inside subscription_status.subscription", async () => {
		api.billing.getPageData.mockResolvedValue({
			dashboard: { usage: { billing: {} } },
			subscription_status: { subscription: { plan: "Team", payment_failure: FAILURE } },
		});
		const { loadData, paymentFailure } = useBillingData();
		await loadData();
		expect(paymentFailure.value).toEqual(FAILURE);
	});

	it("exposes null when nothing is failing", async () => {
		api.billing.getPageData.mockResolvedValue({
			dashboard: { usage: { billing: {} } },
			subscription_status: { subscription: { plan: "Team", payment_failure: null } },
		});
		const { loadData, paymentFailure } = useBillingData();
		await loadData();
		expect(paymentFailure.value).toBeNull();
	});
});
