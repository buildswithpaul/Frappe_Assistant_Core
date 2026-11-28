import { baseCall, getCall } from "../_core";

// Auto-approve mode: everyday changes run without an approval card and are listed in the reply.
// The server row follows the user to every browser.
export const approvalMode = {
	get: () => getCall("frappe_assistant_core.chat.api.get_approval_mode"),

	set: (on) => baseCall("frappe_assistant_core.chat.api.set_approval_mode", { on }),

	// The user has seen the notice that explains the mode; it applies only after this.
	acknowledge: () => baseCall("frappe_assistant_core.chat.api.acknowledge_approval_mode"),
};
