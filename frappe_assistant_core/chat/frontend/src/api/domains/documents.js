import { baseCall, friendlyError, getCall, getCsrfToken, networkError } from "../_core";

export const documents = {
	list: (limit = 50, offset = 0) =>
		getCall("frappe_assistant_core.chat.api.list_documents", {
			limit,
			offset,
		}),

	get: (documentId) =>
		getCall("frappe_assistant_core.chat.api.get_document", {
			document_id: documentId,
		}),

	listChunks: (documentId, { search = null, limit = 50, offset = 0 } = {}) =>
		getCall("frappe_assistant_core.chat.api.list_chunks", {
			document_id: documentId,
			search,
			limit,
			offset,
		}),

	getContentUrl: (documentId) =>
		`/api/method/frappe_assistant_core.chat.api.get_document_content?document_id=${encodeURIComponent(
			documentId
		)}`,

	getDownloadUrl: (documentId) =>
		`/api/method/frappe_assistant_core.chat.api.get_document_content?document_id=${encodeURIComponent(
			documentId
		)}&download=1`,

	upload: async (file, { visibility = null, sharedWith = null } = {}) => {
		const formData = new FormData();
		formData.append("file", file);
		if (visibility) formData.append("visibility", visibility);
		if (sharedWith) formData.append("shared_with", JSON.stringify(sharedWith));

		let response;
		try {
			response = await fetch(
				"/api/method/frappe_assistant_core.chat.api.upload_document",
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
		return data.message;
	},

	delete: (documentId) =>
		baseCall("frappe_assistant_core.chat.api.delete_document", {
			document_id: documentId,
		}),

	updateAccess: (documentId, { visibility = null, addUsers = null, removeUsers = null } = {}) =>
		baseCall("frappe_assistant_core.chat.api.update_document_access", {
			document_id: documentId,
			visibility,
			add_users: addUsers ? JSON.stringify(addUsers) : null,
			remove_users: removeUsers ? JSON.stringify(removeUsers) : null,
		}),

	getStorageInfo: () =>
		getCall("frappe_assistant_core.chat.api.get_storage_info"),
};
