import { baseCall, getCall } from "../_core";

export const notifications = {
	get: () =>
		getCall(
			"frappe_assistant_core.chat.api.notifications.get_notifications"
		),

	dismiss: (notificationId) =>
		baseCall(
			"frappe_assistant_core.chat.api.notifications.dismiss_notification",
			{
				notification_id: notificationId,
			}
		),
};
