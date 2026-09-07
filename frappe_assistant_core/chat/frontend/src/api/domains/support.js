import {
	MSG_GENERIC,
	baseCall,
	buildError,
	friendlyError,
	getCall,
	getCsrfToken,
	networkError,
} from "../_core";

const serializeIds = (ids) => (ids && ids.length > 0 ? JSON.stringify(ids) : null);

export const support = {
	getEnvironment: () =>
		getCall("frappe_assistant_core.chat.api.support.get_environment"),

	createTicket: ({ subject, description, category, conversationId, environment, attachmentIds }) =>
		baseCall("frappe_assistant_core.chat.api.support.create_ticket", {
			subject,
			description,
			category,
			conversation_id: conversationId || null,
			environment: environment ? JSON.stringify(environment) : null,
			attachment_ids: serializeIds(attachmentIds),
		}),

	submitFeedback: ({ rating, comment, category, conversationId, environment }) =>
		baseCall("frappe_assistant_core.chat.api.support.submit_feedback", {
			rating,
			comment,
			category,
			conversation_id: conversationId || null,
			environment: environment ? JSON.stringify(environment) : null,
		}),

	listMyTickets: (status = null) =>
		baseCall("frappe_assistant_core.chat.api.support.list_my_tickets", { status }),

	listMyFeedback: () =>
		baseCall("frappe_assistant_core.chat.api.support.list_my_feedback"),

	getTicketThread: (ticketId) =>
		baseCall("frappe_assistant_core.chat.api.support.get_ticket_thread", {
			ticket_id: ticketId,
		}),

	replyToTicket: (ticketId, message, attachmentIds = []) =>
		baseCall("frappe_assistant_core.chat.api.support.reply_to_ticket", {
			ticket_id: ticketId,
			message,
			attachment_ids: serializeIds(attachmentIds),
		}),

	uploadTicketAttachment: async (file) => {
		const formData = new FormData();
		formData.append("file", file);
		let response;
		try {
			response = await fetch(
				"/api/method/frappe_assistant_core.chat.api.support.upload_ticket_attachment",
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
		const file_dict = data.message?.file || data.message;
		if (!file_dict?.file_id) {
			throw buildError(data.message?.error || MSG_GENERIC, { status: response.status });
		}
		return file_dict;
	},
};
