import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import BillingBanners from "../BillingBanners.vue";

const failure = {
	reason: "Card declined by issuer.",
	failed_at: "2026-10-05 00:02:47",
	invoice: "AR-INV-1",
	dunning_level: "Warning",
	attempt: 1,
	total_attempts: 4,
	next_retry_on: "2026-10-06",
	past_due: false,
};

describe("BillingBanners payment failure", () => {
	it("shows the retrying banner with reason, date and next attempt", async () => {
		const w = mount(BillingBanners, { props: { paymentFailure: failure } });
		const banner = w.find(".payment-retry-banner");
		expect(banner.exists()).toBe(true);
		expect(banner.text()).toContain("Your payment on 5 Oct didn't go through.");
		expect(banner.text()).toContain("Card declined by issuer.");
		expect(banner.text()).toContain("We'll try again on 6 Oct (attempt 2 of 4).");
		await banner.find("button").trigger("click");
		expect(w.emitted("manage-payment")).toHaveLength(1);
	});

	it("adds the reason to the past-due banner instead of a second banner", () => {
		const w = mount(BillingBanners, {
			props: {
				paymentFailed: true,
				paymentFailure: { ...failure, past_due: true, attempt: 4, next_retry_on: null },
			},
		});
		expect(w.find(".payment-retry-banner").exists()).toBe(false);
		expect(w.find(".payment-failed-banner").text()).toContain("Card declined by issuer.");
	});

	it("no block → no new banner (an older payments app)", () => {
		const w = mount(BillingBanners, { props: { paymentFailed: false } });
		expect(w.find(".payment-retry-banner").exists()).toBe(false);
	});

	it("renders a reason as text", () => {
		const w = mount(BillingBanners, {
			props: { paymentFailure: { ...failure, reason: "<b>card</b> declined" } },
		});
		expect(w.find(".payment-retry-banner b").exists()).toBe(false);
		expect(w.find(".payment-retry-banner").text()).toContain("<b>card</b> declined");
	});

	it("leaves out the reason sentence when there is none", () => {
		const w = mount(BillingBanners, { props: { paymentFailure: { ...failure, reason: "" } } });
		expect(w.find(".payment-retry-banner .failure-reason").exists()).toBe(false);
	});
});
