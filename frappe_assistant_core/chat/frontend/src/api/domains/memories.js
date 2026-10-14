import { baseCall, getCall } from "../_core";

export const memories = {
	list: (memoryType = null, limit = 50, offset = 0, project = null) =>
		getCall("frappe_assistant_core.chat.api.list_memories", {
			memory_type: memoryType,
			limit,
			offset,
			...(project ? { project } : {}),
		}),

	delete: (memoryId) =>
		baseCall("frappe_assistant_core.chat.api.delete_memory", {
			memory_id: memoryId,
		}),

	update: (memoryId, content) =>
		baseCall("frappe_assistant_core.chat.api.update_memory", {
			memory_id: memoryId,
			content,
		}),

	clearProject: (project) =>
		baseCall("frappe_assistant_core.chat.api.memories.clear_project_memories", {
			project,
		}),

	deleteAll: () =>
		baseCall("frappe_assistant_core.chat.api.delete_all_memories"),

	getStats: () =>
		getCall("frappe_assistant_core.chat.api.get_memory_stats"),

	getSummary: (force = false) => {
		const params = {};
		if (force) params.force = true;
		return getCall(
			"frappe_assistant_core.chat.api.memories.get_memory_summary",
			params
		);
	},
};
