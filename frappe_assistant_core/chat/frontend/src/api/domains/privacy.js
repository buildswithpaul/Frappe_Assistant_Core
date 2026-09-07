import { baseCall, getCall } from "../_core";

export const privacy = {
	exportData: () =>
		getCall("frappe_assistant_core.chat.api.privacy.export_my_data"),

	eraseData: (password) =>
		baseCall("frappe_assistant_core.chat.api.privacy.erase_my_data", {
			password,
		}),

	restrictProcessing: (restrict = true) =>
		baseCall(
			"frappe_assistant_core.chat.api.privacy.restrict_my_processing",
			{
				restrict,
			}
		),

	updateConsent: (consentType, granted = true) =>
		baseCall(
			"frappe_assistant_core.chat.api.privacy.update_my_consent",
			{
				consent_type: consentType,
				granted,
			}
		),

	getConfig: () =>
		getCall(
			"frappe_assistant_core.chat.api.privacy.get_privacy_config"
		),

	updateConfig: (config) =>
		baseCall(
			"frappe_assistant_core.chat.api.privacy.update_privacy_config",
			{
				config: JSON.stringify(config),
			}
		),

	saveInitialConsent: (memoryConsent) =>
		baseCall(
			"frappe_assistant_core.chat.api.privacy.save_initial_consent",
			{
				memory_consent: memoryConsent,
			}
		),
};
