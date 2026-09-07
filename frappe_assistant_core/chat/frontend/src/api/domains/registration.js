import { baseCall, getCall } from "../_core";

export const registration = {
	getTerms: () => getCall("frappe_assistant_core.chat.api.get_ar_terms"),

	validatePartnerCode: (code) =>
		baseCall("frappe_assistant_core.chat.api.validate_partner_code", {
			referral_code: code,
		}),

	register: (
		ownerEmail,
		termsVersion,
		acceptedBy = null,
		referralCode = null,
		promotionToken = null
	) =>
		baseCall("frappe_assistant_core.chat.api.register_with_ar", {
			owner_email: ownerEmail,
			terms_version: termsVersion,
			accepted_by: acceptedBy,
			referral_code: referralCode,
			promotion_token: promotionToken,
		}),

	getState: () =>
		baseCall("frappe_assistant_core.chat.api.get_registration_state"),

	acceptUpdatedTerms: (termsVersion) =>
		baseCall("frappe_assistant_core.chat.api.accept_updated_terms", {
			terms_version: termsVersion,
		}),

	completeEmailVerification: (verificationToken) =>
		baseCall(
			"frappe_assistant_core.chat.api.complete_email_verification",
			{
				verification_token: verificationToken,
			}
		),

	requestSiteRebind: (newSiteUrl) =>
		baseCall("frappe_assistant_core.chat.api.request_site_rebind", {
			new_site_url: newSiteUrl,
		}),

	pollForRotatedSecret: () =>
		baseCall("frappe_assistant_core.chat.api.poll_for_rotated_secret"),

	runDiagnostics: () =>
		baseCall("frappe_assistant_core.chat.api.run_diagnostics"),
};
