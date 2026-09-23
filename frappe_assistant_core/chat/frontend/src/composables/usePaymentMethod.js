import { ref } from "vue";

import { api } from "@/api/client";
import { logger } from "@/utils/logger";

import { startHostedCheckout } from "./_billing/hostedCheckout";

/**
 * Reading and changing the instrument that pays for the subscription.
 *
 * `update_mode` comes from the backend, which knows whether a renewal is
 * unpaid. The UI never decides between "settle" and "swap" — it forwards
 * the click and opens whatever checkout comes back.
 */
export function usePaymentMethod({
	verificationMessage,
	verificationSuccess,
	invoiceInfo,
	closeGatewayModal,
	loadData,
	billingDetails,
}) {
	const instrument = ref(null);
	const updateMode = ref("swap");
	const amountDue = ref(null);
	// Whether the backend will act on an update click at all — false for a
	// tenant on neither gateway (e.g. Free plan, no payment_gateway set).
	// Defaults true so the button isn't disabled before the first load.
	const canUpdate = ref(true);
	const loadingInstrument = ref(false);
	const updating = ref(false);
	// Distinct from "no instrument" (which is a legitimate, cheerful empty
	// state) — this means the read itself failed, so the tab must say so
	// rather than tell a customer with a working card that they have none.
	const instrumentError = ref(null);
	// The refusal/failure surface for the update click itself. Mirrored
	// into verificationMessage for the top-of-page banner too, but that
	// banner can be scrolled out of view of a button near the bottom of
	// this tab, so the tab needs its own copy.
	const updateError = ref(null);

	async function loadInstrument() {
		loadingInstrument.value = true;
		instrumentError.value = null;
		try {
			const result = await api.billing.getPaymentInstrument();
			if (result?.error) throw new Error(result.error);
			instrument.value = result?.autopay || null;
			updateMode.value = result?.update_mode || "swap";
			amountDue.value = result?.amount_due || null;
			canUpdate.value = result?.can_update !== false;
		} catch (err) {
			logger.error("Payment instrument load error:", err);
			instrument.value = null;
			instrumentError.value = err.message || "Failed to load your payment method";
		} finally {
			loadingInstrument.value = false;
		}
	}

	async function updatePaymentMethod(paymentMethod = null) {
		if (updating.value) return;
		updating.value = true;
		updateError.value = null;
		try {
			const billingEmail = billingDetails.value?.billing_email || null;
			const billingName = billingEmail?.split("@")[0] || null;

			// Whether this is a swap or a settle — and whether it is refused
			// because a debit for this period may still land — is decided on
			// FAC Cloud when the checkout page opens, and reported there.
			await startHostedCheckout("Payment Method", {
				payment_method: paymentMethod,
				billing_name: billingName,
			});
		} catch (err) {
			logger.error("Payment method update error:", err);
			if (err.message !== "Payment cancelled") {
				const message = "Failed to update payment method: " + (err.message || err);
				verificationMessage.value = message;
				verificationSuccess.value = false;
				updateError.value = message;
			}
			await loadInstrument();
		} finally {
			updating.value = false;
		}
	}

	return {
		instrument,
		updateMode,
		amountDue,
		canUpdate,
		loadingInstrument,
		updating,
		instrumentError,
		updateError,
		loadInstrument,
		updatePaymentMethod,
	};
}
