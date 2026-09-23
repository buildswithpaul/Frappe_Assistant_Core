import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import MethodPickerModal from "@/components/settings/billing/payment/MethodPickerModal.vue";

const formatCurrency = (amount, currency) => `${currency} ${amount}`;

// The modal teleports to <body>, so it is the document — not the wrapper —
// that has to be queried.
function mountPicker(props = {}) {
	mount(MethodPickerModal, {
		props: { isOpen: true, formatCurrency, ...props },
	});
	return document.querySelector(".picker-modal");
}

afterEach(() => {
	document.body.replaceChildren();
});

const methodNames = (modal) =>
	[...modal.querySelectorAll("button.method .method-name")].map((el) => el.textContent.trim());

describe("MethodPickerModal method availability", () => {
	it("offers UPI Autopay alongside Card for an INR subscription", () => {
		const modal = mountPicker({ currency: "INR" });
		expect(methodNames(modal)).toEqual(["UPI Autopay", "Card"]);
	});

	it("hides UPI Autopay for a USD subscription", () => {
		// `_resolve_currency_and_method` returns ("USD", "card") for any
		// non-India billing country regardless of what was requested — so an
		// international customer who picked "UPI Autopay — Pay from your bank
		// app" was silently handed a card form.
		const modal = mountPicker({ currency: "USD" });
		expect(methodNames(modal)).toEqual(["Card"]);
	});

	it("reads the currency from an outstanding amount when that is what we have", () => {
		const modal = mountPicker({
			currency: "USD",
			amountDue: { invoice: "AR-INV-1", amount: 49, currency: "USD" },
		});
		expect(methodNames(modal)).toEqual(["Card"]);
		expect(modal.textContent).toContain("USD 49");
	});

	it("keeps both options when the currency is not known", () => {
		// A Razorpay tenant with no saved instrument and nothing owed carries
		// no currency in the payload. Showing both is the pre-existing
		// behaviour; hiding UPI here would cost an Indian customer the
		// default method.
		const modal = mountPicker({ currency: null });
		expect(methodNames(modal)).toEqual(["UPI Autopay", "Card"]);
	});
});

describe("MethodPickerModal copy", () => {
	it("promises the swap authorization is refunded when nothing is due", () => {
		const modal = mountPicker({ currency: "INR" });
		expect(modal.textContent).toContain("refund");
	});

	it("names the amount when something is due", () => {
		const modal = mountPicker({
			currency: "INR",
			amountDue: { invoice: "AR-INV-1", amount: 3540, currency: "INR" },
		});
		expect(modal.textContent).toContain("INR 3540");
	});
});
