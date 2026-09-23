import { baseCall, getCall } from "../_core";

export const sharedKnowledge = {
	get: () =>
		getCall("frappe_assistant_core.chat.api.get_shared_knowledge"),

	update: (content) =>
		baseCall("frappe_assistant_core.chat.api.update_shared_knowledge", {
			content,
		}),

	shareMemory: (memoryId) =>
		baseCall(
			"frappe_assistant_core.chat.api.share_memory_to_knowledge",
			{
				memory_id: memoryId,
			}
		),
};
