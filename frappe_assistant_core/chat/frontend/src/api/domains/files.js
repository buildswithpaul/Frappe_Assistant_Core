import { friendlyError, getCsrfToken, networkError } from "../_core";

export const files = {
	upload: async (file) => {
		const formData = new FormData();
		formData.append("file", file);
		formData.append("is_private", "1");
		formData.append("folder", "Home/FACO");

		let response;
		try {
			response = await fetch("/api/method/upload_file", {
				method: "POST",
				headers: {
					"X-Frappe-CSRF-Token": getCsrfToken(),
				},
				body: formData,
				credentials: "same-origin",
			});
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
};
