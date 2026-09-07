import { baseCall } from "../_core";

// SPA Initialization (combined endpoint — replaces 6 sequential calls)
export const init = {
	initialize: () =>
		baseCall("frappe_assistant_core.chat.api.initialize_spa"),
};
