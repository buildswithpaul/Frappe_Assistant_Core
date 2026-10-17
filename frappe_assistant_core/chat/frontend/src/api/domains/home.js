import { getCall } from "../_core";

export const home = {
	get: () => getCall("frappe_assistant_core.chat.api.get_home_signals"),
};
