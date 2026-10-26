/**
 * How a personal page's calls reach Frappe once pageFrameHost.js has decided to send them.
 */
import { __ } from "@/utils/i18n";

/** Args for a GET query string: Frappe parses JSON-encoded values back on the server. */
export const queryArgs = (args = {}) =>
	Object.fromEntries(
		Object.entries(args)
			.filter(([, value]) => value !== null && value !== undefined)
			.map(([key, value]) => [key, typeof value === "object" ? JSON.stringify(value) : value]),
	);

// The first message Frappe sent with an error, as plain text.
function serverMessage(data) {
	try {
		const first = JSON.parse(JSON.parse(data._server_messages)[0]);
		return String(first.message || first).replace(/<[^>]*>/g, "");
	} catch {
		return typeof data?.exception === "string" ? data.exception.split("\n").pop() : "";
	}
}

/**
 * Sends the frame's calls with fetch, as the user: for the fac-pages Desk page, where frappe.call
 * would open Desk's error dialog over the page for each failed call.
 *
 * @param {() => string} getCsrfToken the session's CSRF token, for a change sent as POST
 */
export function fetchTransport(getCsrfToken) {
	async function send(url, init) {
		const response = await fetch(url, { credentials: "same-origin", ...init });
		let data = null;
		try {
			data = await response.json();
		} catch {
			data = null;
		}
		if (!response.ok || data?.exc) {
			const error = new Error((data && serverMessage(data)) || response.statusText || __("The request failed"));
			error.status = response.status;
			throw error;
		}
		return data?.message;
	}
	return {
		get: (method, args) =>
			send(`/api/method/${method}?${new URLSearchParams(queryArgs(args))}`, {
				method: "GET",
				headers: { Accept: "application/json" },
			}),
		post: (method, args) =>
			send(`/api/method/${method}`, {
				method: "POST",
				headers: {
					Accept: "application/json",
					"Content-Type": "application/json",
					"X-Frappe-CSRF-Token": getCsrfToken(),
				},
				body: JSON.stringify(args || {}),
			}),
	};
}
