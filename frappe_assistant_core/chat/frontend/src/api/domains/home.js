import { baseCall, getCall } from "../_core";

export const home = {
	get: () => getCall("frappe_assistant_core.chat.api.get_home_signals"),
	getPreferences: () => getCall("frappe_assistant_core.chat.api.get_home_preferences"),
	updatePreferences: (patch) => baseCall("frappe_assistant_core.chat.api.update_home_preferences", patch),
	hideSignal: (signalId) => baseCall("frappe_assistant_core.chat.api.hide_home_signal", { signal_id: signalId }),
};
