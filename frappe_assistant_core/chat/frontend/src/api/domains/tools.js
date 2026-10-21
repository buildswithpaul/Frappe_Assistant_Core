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

	// What a message tool will really send, for its approval card. `args` is the
	// tool's previewArgs (e.g. { ticket }).
	messagePreview: (toolName, args = {}) =>
		getCall(
			"frappe_assistant_core.chat.api.message_preview.get_message_preview",
			{ tool_name: toolName, ...args }
		),

	// Stored values of the code fields an update_document call will change, for the old-vs-new diff.
	currentCode: (doctype, name, fields) =>
		getCall(
			"frappe_assistant_core.chat.api.current_code.get_current_code",
			{ doctype, name, fields: JSON.stringify(fields) }
		),

	// Where a Custom Field will land on its form (tab, section, collapsed), for its approval card.
	fieldPlacement: (doctype, insertAfter, fieldtype) =>
		getCall(
			"frappe_assistant_core.chat.api.field_placement.get_field_placement",
			{ doctype, insert_after: insertAfter, fieldtype }
		),
};
