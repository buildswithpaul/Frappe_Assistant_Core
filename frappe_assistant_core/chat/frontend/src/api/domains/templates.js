import { baseCall, getCall } from "../_core";

export const templates = {
	getAll: () =>
		getCall("frappe_assistant_core.chat.api.get_prompt_templates"),

	updatePinned: (pinnedTemplates) =>
		baseCall("frappe_assistant_core.chat.api.update_pinned_templates", {
			pinned_templates: JSON.stringify(pinnedTemplates),
		}),

	getRendered: (promptName, args = {}) =>
		getCall("frappe_assistant_core.chat.api.get_rendered_prompt", {
			prompt_name: promptName,
			arguments: JSON.stringify(args),
		}),
};
