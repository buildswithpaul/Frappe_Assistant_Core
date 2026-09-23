import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";

import PromoCodeSection from "./PromoCodeSection.vue";

/**
 * The savings line hardcoded a "$". That was invisible while AR never
 * populated `discount_amount` -- the dead Stripe price column made the
 * backend's `if plan_price:` always false -- so the bug shipped unseen.
 * Now that AR resolves the price from the tenant's own billing country,
 * the amount arrives in rupees for an Indian tenant, and a "$" in front
 * of it misstates what they save by a factor of ~85.
 */

const mountWith = (appliedPromo) =>
	mount(PromoCodeSection, { props: { appliedPromo } });

describe("PromoCodeSection savings", () => {
	it("denominates the saving in the tenant's own currency", () => {
		const wrapper = mountWith({
			code: "SAVE10",
			display: "10% off",
			discount_amount: 249.9,
			currency: "INR",
		});

		const savings = wrapper.find(".promo-savings").text();
		expect(savings).toContain("₹");
		expect(savings).not.toContain("$");
	});

	it("still renders dollars for a USD tenant", () => {
		const wrapper = mountWith({
			code: "SAVE10",
			display: "10% off",
			discount_amount: 6,
			currency: "USD",
		});

		expect(wrapper.find(".promo-savings").text()).toContain("$6");
	});

	it("falls back to USD when the response carries no currency", () => {
		const wrapper = mountWith({
			code: "SAVE10",
			display: "10% off",
			discount_amount: 6,
		});

		expect(wrapper.find(".promo-savings").text()).toContain("$6");
	});

	it("omits the savings line entirely when there is no discount amount", () => {
		const wrapper = mountWith({ code: "FREETRIAL", display: "14 days free trial" });

		expect(wrapper.find(".promo-savings").exists()).toBe(false);
		expect(wrapper.text()).toContain("14 days free trial");
	});
});
