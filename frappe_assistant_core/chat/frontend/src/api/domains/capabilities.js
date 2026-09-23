import { getCall } from "../_core";

export const capabilities = {
	get: () => getCall("frappe_assistant_core.chat.api.get_capabilities"),
};
