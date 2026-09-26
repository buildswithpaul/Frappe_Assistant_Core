import { baseCall, getCall } from "../_core";

export const billing = {
	getDashboard: () =>
		getCall("frappe_assistant_core.chat.api.get_billing_dashboard"),

	getPageData: (params = {}) =>
		getCall(
			"frappe_assistant_core.chat.api.get_billing_page_data",
			params
		),

	getPlans: () =>
		getCall("frappe_assistant_core.chat.api.get_plan_options"),

	getQuotaStatus: () =>
		getCall("frappe_assistant_core.chat.api.get_quota_status"),

	getAvailableGateways: () =>
		getCall("frappe_assistant_core.chat.api.get_available_gateways"),

	getBillingDetails: () =>
		getCall("frappe_assistant_core.chat.api.get_billing_details"),

	saveBillingDetails: (payload) =>
		baseCall(
			"frappe_assistant_core.chat.api.save_billing_details",
			payload
		),

	previewPlanPricing: (plan, billingCycle = "monthly") =>
		getCall("frappe_assistant_core.chat.api.preview_plan_pricing", {
			plan,
			billing_cycle: billingCycle,
		}),

	previewSeatCharge: () =>
		getCall("frappe_assistant_core.chat.api.preview_seat_charge"),

	addUserSeat: () =>
		baseCall("frappe_assistant_core.chat.api.add_user_seat"),

	// Payments are collected on FAC Cloud's own site, never here — a gateway
	// is onboarded against one declared address, and this app runs on a
	// different domain for every customer. Returns a one-shot checkout_url.
	createHostedCheckout: (purpose, params = {}, returnUrl = null) =>
		baseCall("frappe_assistant_core.chat.api.create_hosted_checkout", {
			purpose,
			params,
			return_url: returnUrl,
		}),

	removeUserSeat: () =>
		baseCall("frappe_assistant_core.chat.api.remove_user_seat"),

	// Opens the PDF in a new tab — the backend streams it with
	// Content-Disposition: attachment, so the browser handles the
	// download automatically. Same-origin + session cookie, so no
	// JS blob dance needed.
	downloadInvoicePdf: (arInvoiceName) => {
		const url = `/api/method/frappe_assistant_core.chat.api.download_invoice_pdf?ar_invoice_name=${encodeURIComponent(
			arInvoiceName
		)}`;
		window.open(url, "_blank");
	},

	initiateUpgrade: (
		plan,
		billingCycle = "monthly",
		gateway = null,
		billingName = null,
		billingEmail = null,
		promoCode = null,
		paymentMethod = null
	) =>
		baseCall("frappe_assistant_core.chat.api.initiate_plan_upgrade", {
			plan,
			billing_cycle: billingCycle,
			gateway,
			billing_name: billingName,
			billing_email: billingEmail,
			promo_code: promoCode,
			payment_method: paymentMethod,
		}),

	// Polled after FAC Cloud's checkout page sends the user back with
	// `?fac_checkout=<session>`; refreshes the cached plan once it lands.
	verifyCheckoutReturn: (session) =>
		baseCall("frappe_assistant_core.chat.api.verify_checkout_return", {
			session,
		}),

	getInvoices: (limit = 10) =>
		getCall("frappe_assistant_core.chat.api.get_invoices", {
			limit,
		}),

	syncSubscription: () =>
		baseCall("frappe_assistant_core.chat.api.sync_subscription_status"),

	getUsageHistory: (days = 30) =>
		getCall("frappe_assistant_core.chat.api.get_usage_history", {
			days,
		}),

	getPaymentMethods: () =>
		getCall("frappe_assistant_core.chat.api.get_payment_methods"),

	// The instrument on file for autopay, plus an `update_mode` of
	// "settle" | "swap" | "portal" telling the UI what the update button
	// will actually do. The backend decides; the UI renders one button.
	getPaymentInstrument: () =>
		getCall("frappe_assistant_core.chat.api.get_payment_instrument"),

	// Starts a checkout that changes the paying instrument. When a renewal
	// is unpaid it settles that invoice and saves the instrument in the same
	// authorization; otherwise it authorizes one currency unit and refunds
	// it. Stripe returns a portal URL instead.
	updatePaymentMethod: (paymentMethod = null, billingName = null) =>
		baseCall("frappe_assistant_core.chat.api.update_payment_method", {
			payment_method: paymentMethod,
			billing_name: billingName,
		}),

	// Re-authorize the saved Razorpay mandate without changing plans.
	// The upgrade endpoint rejects same-plan calls, so this dedicated
	// path goes straight to gateway checkout to mint a fresh token.
	// Surfaced when `subscription.needs_mandate_reauth` is set —
	// either the renewal cron's cap check fired or the bank cancelled
	// the saved token.
	reauthorizeMandate: (billingName = null, paymentMethod = null) =>
		baseCall("frappe_assistant_core.chat.api.reauthorize_mandate", {
			billing_name: billingName,
			payment_method: paymentMethod,
		}),

	cancelSubscription: (cancelImmediately = false) =>
		baseCall("frappe_assistant_core.chat.api.cancel_subscription", {
			cancel_immediately: cancelImmediately,
		}),

	reactivateSubscription: () =>
		baseCall("frappe_assistant_core.chat.api.reactivate_subscription"),

	downgradeToFree: () =>
		baseCall("frappe_assistant_core.chat.api.downgrade_to_free"),

	cancelScheduledChange: () =>
		baseCall("frappe_assistant_core.chat.api.cancel_scheduled_change"),

	verifyRazorpayPayment: (paymentId, subscriptionId, signature) =>
		baseCall("frappe_assistant_core.chat.api.verify_razorpay_payment", {
			razorpay_payment_id: paymentId,
			razorpay_subscription_id: subscriptionId,
			razorpay_signature: signature,
		}),

	validatePromoCode: (code, plan) =>
		getCall(
			"frappe_assistant_core.chat.api.billing.validate_promo_code",
			{
				promo_code: code,
				plan,
			}
		),

	// Prepaid credits
	getCreditBalance: () =>
		getCall("frappe_assistant_core.chat.api.get_credit_balance"),

	purchaseCredits: (creditAmount, gateway = null) =>
		baseCall("frappe_assistant_core.chat.api.purchase_credits", {
			credit_amount: creditAmount,
			gateway,
		}),

	getExpiringCredits: () =>
		getCall("frappe_assistant_core.chat.api.get_expiring_credits"),

	getConsumptionBreakdown: (days = 30) =>
		getCall(
			"frappe_assistant_core.chat.api.get_consumption_breakdown",
			{
				days,
			}
		),

	verifyRazorpayCreditPayment: (paymentId, orderId, signature) =>
		baseCall(
			"frappe_assistant_core.chat.api.verify_razorpay_credit_payment",
			{
				razorpay_payment_id: paymentId,
				razorpay_order_id: orderId,
				razorpay_signature: signature,
			}
		),

	// Verify a Razorpay seat-purchase payment after the widget closes.
	// Stripe seat purchases are confirmed via webhook, not this endpoint.
	verifySeatPayment: (paymentId, orderId, signature) =>
		baseCall("frappe_assistant_core.chat.api.verify_seat_payment", {
			razorpay_payment_id: paymentId,
			razorpay_order_id: orderId,
			razorpay_signature: signature,
		}),
};
