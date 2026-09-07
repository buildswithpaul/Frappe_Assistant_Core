import { baseCall, getCall } from "../_core";

export const tools = {
	listAvailable: () =>
		getCall(
			"frappe_assistant_core.chat.api.tools.list_available_tools"
		),

	listPreferences: () =>
		getCall(
			"frappe_assistant_core.chat.api.tools.list_tool_preferences"
		),

	setPreference: (toolName, preference) =>
		baseCall(
			"frappe_assistant_core.chat.api.tools.set_tool_preference",
			{
				tool_name: toolName,
				preference,
			}
		),
};
