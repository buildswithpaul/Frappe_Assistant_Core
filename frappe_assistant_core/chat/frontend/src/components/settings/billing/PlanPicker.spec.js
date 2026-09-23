import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";

import PlanPicker from "./PlanPicker.vue";

/**
 * The current plan's CTA carried one label over two behaviours: with a change
 * queued it cancelled that change, and without one `handleUpgrade` returned on
 * `planId === currentPlan` and the click did nothing at all. These pin the
 * label to what the click actually does.
 */

const PLANS = [
	{
		id: "pro",
		name: "Pro",
		features: [],
		pricing: {
			currency: "INR",
			currency_symbol: "₹",
			gateway: "razorpay",
			monthly: 5999,
			annual: 59999,
			is_per_user: false,
		},
	},
];

function mountPicker(props = {}) {
	return mount(PlanPicker, {
		props: {
			availablePlans: PLANS,
			currentPlan: "Pro",
			billingCycle: "monthly",
			getPlanPrice: () => "",
			getPlanPriceMeta: (plan) => ({
				kind: "amount",
				symbol: "₹",
				amount: plan.pricing.monthly,
				formatted: "₹5,999",
				period: "/month",
				currency: "INR",
				gateway: "razorpay",
				isPerUser: false,
				minUsers: null,
				minimumTotal: null,
			}),
			getPlanActionText: () => "Upgrade",
			...props,
		},
	});
}

const cta = (wrapper) => wrapper.find("button.cta");

describe("PlanPicker current-plan CTA", () => {
	it("offers to manage the subscription when nothing is queued", async () => {
		const wrapper = mountPicker();

		expect(cta(wrapper).text()).toBe("Manage");

		await cta(wrapper).trigger("click");

		// Must not re-enter checkout for a plan already held — that path is the
		// one `handleUpgrade` silently discards.
		expect(wrapper.emitted("manage-subscription")).toHaveLength(1);
		expect(wrapper.emitted("upgrade")).toBeUndefined();
	});

	it("offers to keep the plan when a change is queued, and undoes it", async () => {
		const wrapper = mountPicker({ hasScheduledChange: true });

		expect(cta(wrapper).text()).toBe("Keep This Plan");

		await cta(wrapper).trigger("click");

		// Cancelling a queued change rides the upgrade path, which routes it to
		// handleCancelScheduledChange.
		expect(wrapper.emitted("upgrade")).toHaveLength(1);
		expect(wrapper.emitted("manage-subscription")).toBeUndefined();
	});

	it("still sends a plan you do not hold to checkout", async () => {
		const wrapper = mountPicker({ currentPlan: "Basic" });

		expect(cta(wrapper).text()).toBe("Upgrade");

		await cta(wrapper).trigger("click");

		expect(wrapper.emitted("upgrade")).toHaveLength(1);
		expect(wrapper.emitted("manage-subscription")).toBeUndefined();
	});

	it("keeps the CTA frozen while cancellation is pending", async () => {
		const wrapper = mountPicker({ planChangesLocked: true });

		expect(cta(wrapper).text()).toBe("Current Plan");
		expect(cta(wrapper).attributes("disabled")).toBeDefined();
	});
});
