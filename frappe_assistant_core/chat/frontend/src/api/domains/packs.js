import { baseCall, getCall } from "../_core";

const BASE = "frappe_assistant_core.chat.api.packs";

export const packs = {
	list: () => getCall(`${BASE}.list_packs`),
	getContents: (pack_id) => getCall(`${BASE}.get_pack_contents`, { pack_id }),
	setEnabled: (pack_id, enabled, source = "User") =>
		baseCall(`${BASE}.set_pack_enabled`, {
			pack_id,
			enabled: enabled ? 1 : 0,
			source,
		}),
	setIndustry: (industry, autoEnable = true) =>
		baseCall(`${BASE}.set_industry`, {
			industry,
			auto_enable: autoEnable ? 1 : 0,
		}),
	getRecommended: () => getCall(`${BASE}.get_recommended_pack`),
	dismissRecommendation: () => baseCall(`${BASE}.dismiss_pack_recommendation`),

	// Paid packs v2
	activateFree: (pack_id) =>
		baseCall(`${BASE}.activate_free_pack`, { pack_id }),
	togglePurchased: (pack_id, enabled) =>
		baseCall(`${BASE}.toggle_purchased_pack`, {
			pack_id,
			enabled: enabled ? 1 : 0,
		}),
	initiateCheckout: (pack_id) =>
		baseCall(`${BASE}.initiate_pack_checkout`, { pack_id }),
	verifyPayment: ({ razorpay_payment_id, razorpay_order_id, razorpay_signature }) =>
		baseCall(`${BASE}.verify_pack_payment`, {
			razorpay_payment_id,
			razorpay_order_id,
			razorpay_signature,
		}),
	listPurchases: () => getCall(`${BASE}.list_pack_purchases`),
};
