import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ref } from "vue";

vi.mock("@/api/client", () => ({
	api: {
		billing: {
			getPaymentInstrument: vi.fn(),
			createHostedCheckout: vi.fn(),
		},
	},
}));

import { api } from "@/api/client";
import { usePaymentMethod } from "@/composables/usePaymentMethod.js";

function harness() {
	const ctx = {
		verificationMessage: ref(null),
		verificationSuccess: ref(null),
		invoiceInfo: ref(null),
		closeGatewayModal: vi.fn(),
		loadData: vi.fn(),
		billingDetails: ref({ billing_email: "paul@example.com" }),
	};
	return { ctx, pm: usePaymentMethod(ctx) };
}

/** Capture where the browser was sent instead of actually navigating. */
function stubNavigation() {
	const went = { to: null };
	vi.stubGlobal("window", {
		...globalThis.window,
		location: {
			href: "https://books.acme.example/app/billing",
			set href(v) {
				went.to = v;
			},
			get href() {
				return "https://books.acme.example/app/billing";
			},
		},
	});
	return went;
}

describe("usePaymentMethod", () => {
	beforeEach(() => {
		api.billing.getPaymentInstrument.mockReset();
		api.billing.createHostedCheckout.mockReset();
		// Every update path ends by re-reading the instrument.
		api.billing.getPaymentInstrument.mockResolvedValue({ update_mode: "swap" });
	});
	afterEach(() => vi.restoreAllMocks());

	describe("loadInstrument", () => {
		it("maps a settle payload onto the tab's state", async () => {
			const { pm } = harness();
			api.billing.getPaymentInstrument.mockResolvedValue({
				autopay: { label: "UPI Autopay", display: "paul@okhdfcbank" },
				update_mode: "settle",
				amount_due: { invoice: "AR-INV-1", amount: 3540, currency: "INR" },
				can_update: true,
			});

			await pm.loadInstrument();

			expect(pm.instrument.value.display).toBe("paul@okhdfcbank");
			expect(pm.updateMode.value).toBe("settle");
			expect(pm.amountDue.value.amount).toBe(3540);
			expect(pm.canUpdate.value).toBe(true);
			expect(pm.instrumentError.value).toBeNull();
			expect(pm.loadingInstrument.value).toBe(false);
		});
	});

	describe("updating the instrument", () => {
		it("asks FAC Cloud for a checkout link rather than opening a widget here", async () => {
			// The whole point of the change: a payment gateway is onboarded
			// against one declared website, and this app runs on a different
			// domain for every customer.
			const { pm } = harness();
			const went = stubNavigation();
			api.billing.createHostedCheckout.mockResolvedValue({
				checkout_url: "https://pay.example/checkout?token=abc",
			});

			await pm.updatePaymentMethod("upi");

			expect(api.billing.createHostedCheckout).toHaveBeenCalledWith(
				"Payment Method",
				{ payment_method: "upi", billing_name: "paul" },
				"https://books.acme.example/app/billing",
			);
			expect(went.to).toBe("https://pay.example/checkout?token=abc");
		});

		it("refuses a checkout link a browser would not protect", async () => {
			const { pm } = harness();
			stubNavigation();
			api.billing.createHostedCheckout.mockResolvedValue({
				checkout_url: "http://pay.evil.example/checkout?token=abc",
			});

			await pm.updatePaymentMethod();

			expect(pm.updateError.value).toContain("https");
		});
	});

	describe("refusals and failures", () => {
		it("reports a thrown error and re-reads the instrument", async () => {
			const { pm, ctx } = harness();
			api.billing.createHostedCheckout.mockRejectedValue(new Error("network down"));

			await pm.updatePaymentMethod();

			expect(pm.updateError.value).toContain("network down");
			expect(ctx.verificationSuccess.value).toBe(false);
			expect(api.billing.getPaymentInstrument).toHaveBeenCalled();
			expect(pm.updating.value).toBe(false);
		});

		it("errors when no link comes back", async () => {
			const { pm } = harness();
			api.billing.createHostedCheckout.mockResolvedValue({});

			await pm.updatePaymentMethod();

			expect(pm.updateError.value).toContain("Could not start checkout");
		});
	});
});
