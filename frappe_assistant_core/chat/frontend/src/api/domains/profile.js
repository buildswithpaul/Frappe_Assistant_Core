import { baseCall, getCall } from "../_core";

export const profile = {
	get: () => getCall("frappe_assistant_core.chat.api.get_profile"),

	update: (fields) =>
		baseCall("frappe_assistant_core.chat.api.update_profile", fields),
};
