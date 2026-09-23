import { getCall } from "../_core";

export const suggestions = {
	get: (context = {}) =>
		getCall("frappe_assistant_core.chat.api.get_suggested_prompts", {
			context: JSON.stringify(context),
		}),
};
