import { ref } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import PaymentMethodTab from "@/components/settings/billing/payment/PaymentMethodTab.vue";

const formatCurrency = (amount, currency) => `${currency} ${amount}`;

/** A fake usePaymentMethod() — the composable's own contract is tested
 * elsewhere; here we only need something that behaves like its refs. */
function fakePaymentMethod(overrides = {}) {
	const base = {
		instrument: ref(null),
		updateMode: ref("swap"),
		amountDue: ref(null),
		canUpdate: ref(true),
		loadingInstrument: ref(false),
		updating: ref(false),
		instrumentError: ref(null),
		updateError: ref(null),
		loadInstrument: vi.fn(),
		updatePaymentMethod: vi.fn(),
		...overrides,
	};
	return base;
}

function mountTab(paymentMethod) {
	return mount(PaymentMethodTab, {
		props: { formatCurrency, paymentMethod },
	});
}

describe("PaymentMethodTab error state", () => {
	it("renders the error state on load failure rather than the empty state", async () => {
		const paymentMethod = fakePaymentMethod({
			loadInstrument: vi.fn(async () => {
				// A non-admin / unregistered-tenant / AR-unreachable failure —
				// instrument stays null, same as the legitimate empty state.
				paymentMethod.instrument.value = null;
				paymentMethod.instrumentError.value = "Failed to load your payment method";
			}),
		});

		const w = mountTab(paymentMethod);
		await flushPromises();

		expect(paymentMethod.loadInstrument).toHaveBeenCalled();
		expect(w.find(".tab-error").exists()).toBe(true);
		expect(w.text()).toContain("Failed to load your payment method");
		// The two states must never look the same — a customer with a
		// working card must not be told they have none.
		expect(w.text()).not.toContain("No payment method is saved yet");
		expect(w.findComponent({ name: "AutopayCard" }).exists()).toBe(false);
	});

	it("retry re-invokes loadInstrument", async () => {
		const paymentMethod = fakePaymentMethod({
			instrumentError: ref("Could not reach billing"),
		});
		const w = mountTab(paymentMethod);
		await flushPromises();

		await w.find(".retry-btn").trigger("click");
		// Once on mount, once from the retry click.
		expect(paymentMethod.loadInstrument).toHaveBeenCalledTimes(2);
	});
});

describe("PaymentMethodTab success state", () => {
	it("renders AutopayCard and no error chrome once the load succeeds", async () => {
		const paymentMethod = fakePaymentMethod({
			instrument: ref({
				status: "Active", label: "Card", display: "Visa •••• 4242",
				card: null, next_charge_date: null, max_amount: null,
				needs_reauth: false, suspended: false,
			}),
		});
		const w = mountTab(paymentMethod);
		await flushPromises();

		expect(w.find(".tab-error").exists()).toBe(false);
		expect(w.findComponent({ name: "AutopayCard" }).exists()).toBe(true);
	});

	it("surfaces a refusal inline, next to the card, not just in the global banner", async () => {
		const paymentMethod = fakePaymentMethod({
			instrument: ref({
				status: "Active", label: "Card", display: "Visa •••• 4242",
				card: null, next_charge_date: null, max_amount: null,
				needs_reauth: false, suspended: false,
			}),
			updateMode: ref("portal"),
			updatePaymentMethod: vi.fn(async () => {
				paymentMethod.updateError.value = "A charge for this period may still settle.";
			}),
		});
		const w = mountTab(paymentMethod);
		await flushPromises();

		await w.find("button.update-btn").trigger("click");
		await flushPromises();

		expect(paymentMethod.updatePaymentMethod).toHaveBeenCalled();
		expect(w.find(".update-error").exists()).toBe(true);
		expect(w.text()).toContain("A charge for this period may still settle.");
	});
});

describe("PaymentMethodTab picker currency", () => {
	const usdInstrument = {
		status: "Active", label: "Card", display: "Visa •••• 4242", currency: "USD",
		card: null, next_charge_date: null, max_amount: null,
		needs_reauth: false, suspended: false,
	};

	it("prefers the outstanding invoice's currency over the instrument's", async () => {
		const paymentMethod = fakePaymentMethod({
			instrument: ref({ ...usdInstrument, currency: "INR" }),
			updateMode: ref("settle"),
			amountDue: ref({ invoice: "AR-INV-1", amount: 49, currency: "USD" }),
		});
		const w = mountTab(paymentMethod);
		await flushPromises();

		expect(w.findComponent({ name: "MethodPickerModal" }).props("currency")).toBe("USD");
	});

	it("falls back to the saved instrument's currency", async () => {
		const paymentMethod = fakePaymentMethod({ instrument: ref(usdInstrument) });
		const w = mountTab(paymentMethod);
		await flushPromises();

		expect(w.findComponent({ name: "MethodPickerModal" }).props("currency")).toBe("USD");
	});

	it("passes null when neither is known", async () => {
		const paymentMethod = fakePaymentMethod();
		const w = mountTab(paymentMethod);
		await flushPromises();

		expect(w.findComponent({ name: "MethodPickerModal" }).props("currency")).toBeNull();
	});
});

describe("PaymentMethodTab loading state", () => {
	it("shows the loading copy while the instrument is still being read", () => {
		const paymentMethod = fakePaymentMethod({ loadingInstrument: ref(true) });
		const w = mountTab(paymentMethod);
		expect(w.find(".loading").exists()).toBe(true);
		expect(w.findComponent({ name: "AutopayCard" }).exists()).toBe(false);
	});
});
