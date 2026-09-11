import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";

/**
 * The screen that takes the money has to be right about what the money buys.
 *
 * This copy read "They never expire and carry over across billing cycles."
 * That was true until purchases gained a validity window, at which point the
 * buy screen was making a false promise about the customer's money. The
 * window is configurable, so the number is published with the pack price
 * rather than restated here — a hardcoded "12 months" outlives a changed
 * setting silently, and the drift lands on the one screen where it is a
 * mis-sale rather than a cosmetic error.
 */

import CreditPurchaseModal from "../CreditPurchaseModal.vue";

function gateway(overrides = {}) {
	return {
		name: "razorpay",
		display_name: "Razorpay",
		currency: "INR",
		currency_symbol: "₹",
		is_recommended: true,
		plans: {},
		pack_credits: 2000,
		pack_price: 500,
		...overrides,
	};
}

function render(gw) {
	return mount(CreditPurchaseModal, {
		props: { isOpen: true, gateways: [gw] },
		global: { stubs: { Teleport: true } },
	});
}

function description(wrapper) {
	return wrapper.find(".credit-description").text().replace(/\s+/g, " ").trim();
}

describe("CreditPurchaseModal validity disclosure", () => {
	it("tells the buyer how long the credits last", () => {
		const text = description(render(gateway({ credit_validity_months: 12 })));
		expect(text).toContain("12 months");
		expect(text).not.toMatch(/never expire/i);
	});

	it("follows the configured window rather than a hardcoded year", () => {
		expect(description(render(gateway({ credit_validity_months: 6 })))).toContain("6 months");
	});

	it("says they do not expire when the window is switched off", () => {
		const text = description(render(gateway({ credit_validity_months: 0 })));
		expect(text).toContain("do not expire");
	});

	it("claims nothing at all when the server did not say", () => {
		// An AR that predates the window. Both guesses are a statement about
		// the buyer's money, so the screen makes neither.
		const text = description(render(gateway()));
		expect(text).not.toMatch(/expire/i);
		expect(text).not.toMatch(/stay valid/i);
		expect(text).toContain("carry over across billing cycles");
	});

	it("still says the part that is true regardless", () => {
		const text = description(render(gateway({ credit_validity_months: 12 })));
		expect(text).toContain("after your monthly quota is exhausted");
	});
});
