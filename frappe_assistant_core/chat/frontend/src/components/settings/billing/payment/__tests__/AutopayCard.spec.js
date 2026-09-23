import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AutopayCard from "@/components/settings/billing/payment/AutopayCard.vue";

const formatCurrency = (amount, currency) => `${currency} ${amount}`;

const RAZORPAY_MANDATE = {
	mandate: "MND-1",
	status: "Active",
	method: "upi",
	label: "UPI Autopay",
	display: "paul@okhdfcbank",
	card: null,
	vpa: "paul@okhdfcbank",
	bank: "HDFC Bank",
	max_amount: 29990,
	currency: "INR",
	authorized_on: "2026-03-14",
	next_charge_date: "2026-09-14",
	needs_reauth: false,
	suspended: false,
};

const STRIPE_INSTRUMENT = {
	mandate: null,
	status: "Active",
	method: "card",
	label: "Card",
	display: "Visa •••• 4242",
	card: { last4: "4242", network: "visa", issuer: null, expiry: "09/2028" },
	vpa: null,
	bank: null,
	max_amount: null,
	currency: "USD",
	authorized_on: null,
	next_charge_date: "2026-09-14",
	needs_reauth: null,
	suspended: false,
};

function mountCard(props = {}) {
	return mount(AutopayCard, {
		props: {
			instrument: null,
			updateMode: "swap",
			amountDue: null,
			updating: false,
			formatCurrency,
			...props,
		},
	});
}

describe("AutopayCard pill mapping", () => {
	it("shows warn when needs_reauth is true", () => {
		const w = mountCard({ instrument: { ...RAZORPAY_MANDATE, needs_reauth: true } });
		const pill = w.find(".status-pill");
		expect(pill.classes()).toContain("warn");
		expect(pill.text()).toBe("Needs re-authorization");
	});

	it("shows warn when suspended is true", () => {
		const w = mountCard({ instrument: { ...RAZORPAY_MANDATE, suspended: true } });
		const pill = w.find(".status-pill");
		expect(pill.classes()).toContain("warn");
		expect(pill.text()).toBe("Account suspended");
	});

	it("never renders a success pill for an unhealthy status it doesn't recognise (Finding 1)", () => {
		// Stripe's PastDue subscription: needs_reauth is hard-null (Razorpay-only
		// concept) and suspended is false until dunning actually escalates — the
		// two booleans the pill is allowed to branch on both say "no problem",
		// even though the raw status says otherwise. The pill must not claim "ok".
		const w = mountCard({
			instrument: { ...STRIPE_INSTRUMENT, status: "PastDue", needs_reauth: null, suspended: false },
		});
		const pill = w.find(".status-pill");
		expect(pill.classes()).not.toContain("ok");
		expect(pill.classes()).not.toContain("warn");
		expect(pill.classes()).toContain("neutral");
		expect(pill.text()).toBe("PastDue");
	});

	it("renders a healthy Razorpay mandate as neutral, not a claimed 'ok'", () => {
		const w = mountCard({ instrument: RAZORPAY_MANDATE });
		const pill = w.find(".status-pill");
		expect(pill.classes()).not.toContain("ok");
		expect(pill.classes()).toContain("neutral");
		expect(pill.text()).toBe("Active");
	});
});

describe("AutopayCard Stripe render", () => {
	it("renders sensibly with every Razorpay-only field null, and no literal 'null' text", () => {
		const w = mountCard({
			instrument: STRIPE_INSTRUMENT,
			updateMode: "portal",
			amountDue: null,
		});

		expect(w.text()).not.toContain("null");
		expect(w.text()).toContain("Visa •••• 4242");
		// max_amount is null on Stripe — "Authorized up to" must not appear.
		expect(w.text()).not.toContain("Authorized up to");
		// card.expiry and next_charge_date are present — those facts do show.
		expect(w.text()).toContain("09/2028");
		expect(w.text()).toContain("2026-09-14");
		expect(w.find("button.update-btn").text()).toBe("Manage in payment portal");
	});

	it("omits the facts list entirely when every fact is null", () => {
		const w = mountCard({
			instrument: { ...STRIPE_INSTRUMENT, card: null, next_charge_date: null, max_amount: null },
			updateMode: "portal",
		});
		expect(w.find("dl.facts").exists()).toBe(false);
	});

	it("omits the fine-print paragraph in portal mode (empty string)", () => {
		const w = mountCard({ instrument: STRIPE_INSTRUMENT, updateMode: "portal" });
		expect(w.find("p.fine-print").exists()).toBe(false);
	});
});

describe("AutopayCard empty state", () => {
	it("shows the empty-state copy when there is no instrument", () => {
		const w = mountCard({ instrument: null });
		expect(w.find(".empty").text()).toContain("No payment method is saved yet");
		expect(w.find(".instrument").exists()).toBe(false);
		expect(w.find(".status-pill").exists()).toBe(false);
	});

	it("empty-state copy is distinct from an error message — it never claims failure", () => {
		const w = mountCard({ instrument: null });
		const text = w.find(".empty").text();
		expect(text).not.toMatch(/fail|error|unable|could not/i);
	});

	it("points a Stripe tenant at the portal, not at the plan picker", () => {
		// "Choose a plan to set one up" sat directly above a button reading
		// "Manage in payment portal" — two different instructions for the
		// same next step, one of which does not apply.
		const w = mountCard({ instrument: null, updateMode: "portal" });
		const text = w.find(".empty").text();
		expect(text).toContain("payment portal");
		expect(text).not.toContain("Choose a plan");
	});

	it("tells a settling tenant the payment below will save the method", () => {
		const w = mountCard({
			instrument: null,
			updateMode: "settle",
			amountDue: { invoice: "AR-INV-1", amount: 3540, currency: "INR" },
		});
		expect(w.find(".empty").text()).toContain("outstanding");
		expect(w.find(".empty").text()).not.toContain("Choose a plan");
	});

	it("keeps the plan-picker pointer for an account that cannot update at all", () => {
		// `can_update: false` means no gateway is attached — a Free plan.
		// Choosing a plan really is the only way to get an instrument.
		const w = mountCard({ instrument: null, canUpdate: false });
		expect(w.find(".empty").text()).toContain("Choose a plan");
	});
});

describe("AutopayCard buttonText per updateMode", () => {
	it("settle", () => {
		const w = mountCard({ instrument: RAZORPAY_MANDATE, updateMode: "settle" });
		expect(w.find("button.update-btn").text()).toBe("Pay now with a new method");
	});

	it("swap with an instrument on file", () => {
		const w = mountCard({ instrument: RAZORPAY_MANDATE, updateMode: "swap" });
		expect(w.find("button.update-btn").text()).toBe("Change payment method");
	});

	it("swap with no instrument on file", () => {
		const w = mountCard({ instrument: null, updateMode: "swap" });
		expect(w.find("button.update-btn").text()).toBe("Add a payment method");
	});

	it("portal", () => {
		const w = mountCard({ instrument: STRIPE_INSTRUMENT, updateMode: "portal" });
		expect(w.find("button.update-btn").text()).toBe("Manage in payment portal");
	});

	it("updating overrides every mode", () => {
		const w = mountCard({ instrument: RAZORPAY_MANDATE, updateMode: "settle", updating: true });
		expect(w.find("button.update-btn").text()).toBe("Opening…");
	});
});

describe("AutopayCard canUpdate", () => {
	it("disables the button and explains why when the backend refuses updates", () => {
		const w = mountCard({ instrument: null, canUpdate: false });
		expect(w.find("button.update-btn").attributes("disabled")).toBeDefined();
		expect(w.find("p.fine-print").text()).toContain("aren't available");
	});

	it("leaves the button enabled by default", () => {
		const w = mountCard({ instrument: RAZORPAY_MANDATE });
		expect(w.find("button.update-btn").attributes("disabled")).toBeUndefined();
	});
});
