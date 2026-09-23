import {
	MSG_GENERIC,
	baseCall,
	buildError,
	friendlyError,
	getCall,
	getCsrfToken,
	networkError,
} from "../_core";

export const chat = {
	send: (
		sessionId,
		message,
		fileUrls = [],
		context = null,
		modelId = null,
		systemPromptAddendum = null,
		attachments = [],
		options = {}
	) =>
		baseCall("frappe_assistant_core.chat.api.send_message", {
			session_id: sessionId,
			message,
			file_urls: fileUrls.length > 0 ? JSON.stringify(fileUrls) : null,
			context,
			model_id: modelId,
			system_prompt_addendum: systemPromptAddendum,
			attachments: attachments.length > 0 ? JSON.stringify(attachments) : null,
			client_type: "spa",
			...options,
		}),

	cancelStream: (sessionId, messageId = null) =>
		baseCall("frappe_assistant_core.chat.api.cancel_stream", {
			session_id: sessionId,
			message_id: messageId,
		}),

	continueResponse: (sessionId, messageId, options = {}) =>
		baseCall("frappe_assistant_core.chat.api.chat.continue_response", {
			session_id: sessionId,
			message_id: messageId,
			client_type: "spa",
			...options,
		}),

	uploadFile: async (file) => {
		const formData = new FormData();
		formData.append("file", file);
		let response;
		try {
			response = await fetch(
				"/api/method/frappe_assistant_core.chat.api.upload_message_file",
				{
					method: "POST",
					headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
					body: formData,
					credentials: "same-origin",
				}
			);
		} catch (cause) {
			throw networkError(cause);
		}
		if (!response.ok) {
			const body = await response.text();
			throw friendlyError(response, body);
		}
		const data = await response.json();
		if (!data.message?.success) {
			throw buildError(data.message?.error || MSG_GENERIC, {
				status: response.status,
			});
		}
		return data.message.file;
	},

	getSessions: (limit = 20) =>
		getCall("frappe_assistant_core.chat.api.get_user_sessions", {
			limit,
		}),

	getMessages: (sessionId) =>
		getCall("frappe_assistant_core.chat.api.get_session_history", {
			session_id: sessionId,
		}),

	createSession: () =>
		baseCall("frappe_assistant_core.chat.api.create_session"),

	archiveSession: (sessionId) =>
		baseCall("frappe_assistant_core.chat.api.archive_session", {
			session_id: sessionId,
		}),

	// Backward compat alias
	deleteSession: (sessionId) =>
		baseCall("frappe_assistant_core.chat.api.archive_session", {
			session_id: sessionId,
		}),

	archiveAllConversations: () =>
		baseCall(
			"frappe_assistant_core.chat.api.archive_all_conversations"
		),

	getArchivedSessions: (limit = 50) =>
		getCall("frappe_assistant_core.chat.api.get_archived_sessions", {
			limit,
		}),

	continueArchivedSession: (oldSessionId) =>
		baseCall(
			"frappe_assistant_core.chat.api.continue_archived_session",
			{
				old_session_id: oldSessionId,
			}
		),
};
