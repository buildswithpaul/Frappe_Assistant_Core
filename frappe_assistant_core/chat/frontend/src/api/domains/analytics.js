import { getCall } from "../_core";

export const analytics = {
	getData: (days = 30) =>
		getCall("frappe_assistant_core.chat.api.get_analytics_data", {
			days,
		}),

	getMyUsage: (days = 30) =>
		getCall("frappe_assistant_core.chat.api.get_my_usage", {
			days,
		}),

	getConversations: (days = 30, limit = 50, offset = 0) =>
		getCall(
			"frappe_assistant_core.chat.api.get_conversation_analytics",
			{
				days,
				limit,
				offset,
			}
		),

	getMessageCredits: (conversationId) =>
		getCall("frappe_assistant_core.chat.api.get_message_credits", {
			conversation_id: conversationId,
		}),
};
