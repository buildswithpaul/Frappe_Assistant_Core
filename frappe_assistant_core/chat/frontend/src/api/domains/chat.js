import {
	MSG_GENERIC,
	baseCall,
	buildError,
	friendlyError,
	getCall,
	getCsrfToken,
	networkError,
} from "../_core";
import { __ } from "@/utils/i18n";

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

	cancelStream: (sessionId, messageId = null, clientTurnId = null) =>
		baseCall("frappe_assistant_core.chat.api.cancel_stream", {
			session_id: sessionId,
			message_id: messageId,
			client_turn_id: clientTurnId,
		}),

	// Resolves { success } or { success: false, reason }; throws when the caller may not undo it.
	undoChange: (sessionId, messageId, doctype, name) =>
		baseCall("frappe_assistant_core.chat.api.changes.undo_change", {
			session_id: sessionId,
			message_id: messageId,
			doctype,
			name,
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
		if (response.status === 413) {
			// Frappe's request limit, met before FACO's own check: an HTML page, not a message
			throw buildError(__("The file is larger than this site's upload limit."), { status: 413 });
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

	getSessions: ({ limit = 30, offset = 0, project = null, search = null } = {}) =>
		getCall("frappe_assistant_core.chat.api.chat.sessions.get_user_sessions", {
			limit,
			offset,
			...(project ? { project } : {}),
			...(search ? { search } : {}),
		}),

	renameSession: (sessionId, title) =>
		baseCall("frappe_assistant_core.chat.api.chat.sessions.rename_session", {
			session_id: sessionId,
			title,
		}),

	moveSessionToProject: (sessionId, project) =>
		baseCall("frappe_assistant_core.chat.api.chat.sessions.move_session_to_project", {
			session_id: sessionId,
			project: project || null,
		}),

	getMessages: (sessionId) =>
		getCall("frappe_assistant_core.chat.api.get_session_history", {
			session_id: sessionId,
		}),

	// The running turn's snapshot, or null — what a surface opening the
	// conversation mid-turn needs to show it and keep streaming.
	claimLiveTurn: (sessionId) =>
		baseCall("frappe_assistant_core.chat.api.chat.claim_live_turn", {
			session_id: sessionId,
		}),

	getLiveTurn: (sessionId) =>
		getCall("frappe_assistant_core.chat.api.chat.get_live_turn", {
			session_id: sessionId,
		}),

	// Runs the latest user message's errored turn again; refused for a turn that completed.
	retryTurn: (sessionId, userMessage, options = {}) =>
		baseCall("frappe_assistant_core.chat.api.chat.retry_turn", {
			session_id: sessionId,
			user_message: userMessage,
			client_type: "spa",
			...options,
		}),

	// Ends a turn whose relay died; the server refuses one that is still running.
	markTurnInterrupted: (sessionId) =>
		baseCall("frappe_assistant_core.chat.api.chat.mark_turn_interrupted", {
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
