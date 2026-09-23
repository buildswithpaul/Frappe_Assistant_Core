/**
 * FACO API core — shared transport, CSRF, error mapping.
 *
 * Domain modules under `api/domains/` import `baseCall` / `getCall` from
 * here. The public `api` object in `api/client.js` aggregates those
 * domains. No domain talks to `fetch` directly except for file-upload
 * helpers, which use the exported error helpers below.
 */

import { logger } from "@/utils/logger";

// FACO-M6: prefer the meta tag embedded in the SPA shell (rendered by
// www/copilot.py::get_context) over the cookie fallback. The cookie is
// readable by any same-origin XSS; the meta tag is captured once at load
// time into a module-private closure so later XSS can't rewrite it.
const _csrfAtLoad =
	document.querySelector('meta[name="csrf-token"]')?.content ||
	window.csrf_token ||
	window.frappe?.csrf_token ||
	"";

export const getCsrfToken = () => _csrfAtLoad || "";

// User-facing strings. Kept as module constants so we can translate them
// in one place if FACO ever gets a translation helper on the frontend.
const MSG_NETWORK = "Can't reach the server. Check your connection and try again.";
const MSG_SESSION = "Your session has ended. Please refresh the page to sign in again.";
export const MSG_GENERIC = "Something went wrong. Please try again.";

// Exception class names that indicate a backend bug or misconfiguration
// rather than a user-facing validation condition. When the response
// carries one of these we show the generic fallback even if Frappe
// happened to pack technical-sounding text into _server_messages.
const TECHNICAL_EXC_TYPES = [
	"AppNotInstalledError",
	"ImportError",
	"ModuleNotFoundError",
	"AttributeError",
	"KeyError",
	"TypeError",
	"NameError",
	"SyntaxError",
];

// Frappe sometimes surfaces framework failures (missing whitelist path,
// AttributeError, etc.) as ValidationError/_server_messages text rather
// than a typed technical exc_type. Match those phrases so we never toast
// "Failed to get method for command … has no attribute …" at users.
const TECHNICAL_MESSAGE_RE =
	/Failed to get method for command|has no attribute|Traceback \(most recent call last\)|ModuleNotFoundError|ImportError|AttributeError|Internal Server Error|DoesNotExistError:.*\bmodule\b/i;

// Repeated to a fixpoint, not replaced once: removing a tag can splice a new
// one together out of what surrounded it, so "<scr<script>ipt>" survives a
// single pass as "<script>".
const stripHtml = (s) => {
	let text = String(s ?? "");
	let previous;
	do {
		previous = text;
		text = text.replace(/<[^>]*>/g, "");
	} while (text !== previous);
	return text.trim();
};

// Frappe's _server_messages is triple-encoded: the response body is JSON,
// _server_messages is a JSON string, and its value is an array of JSON
// strings each of which decodes to {message, title, indicator}. Each
// decode step can fail independently — we tolerate every failure and
// fall through to null so the caller can move to the next rule.
const extractFrappeMessage = (bodyText) => {
	if (!bodyText) return null;
	try {
		const body = JSON.parse(bodyText);
		const raw = body?._server_messages;
		if (!raw) return null;
		const arr = typeof raw === "string" ? JSON.parse(raw) : raw;
		if (!Array.isArray(arr) || arr.length === 0) return null;
		const firstRaw = arr[0];
		const first = typeof firstRaw === "string" ? JSON.parse(firstRaw) : firstRaw;
		const msg = stripHtml(first?.message).replace(/^\[HTTP_\d{3}\]\s*/, "");
		return msg || null;
	} catch {
		return null;
	}
};

// A validation error can name the input that caused it. The server puts the
// field on the response body (see billing_details._reject); surfacing it here
// lets a form attach the message to that input rather than show a banner the
// user has to map onto a field themselves.
const extractFieldName = (bodyText) => {
	if (!bodyText) return null;
	try {
		const body = JSON.parse(bodyText);
		return body?.billing_field || null;
	} catch {
		return null;
	}
};

const hasTechnicalException = (bodyText) => {
	if (!bodyText) return false;
	try {
		const body = JSON.parse(bodyText);
		const excType = body?.exc_type || "";
		const exception = body?.exception || "";
		if (TECHNICAL_EXC_TYPES.some((t) => excType === t || exception.includes(t))) {
			return true;
		}
		// Scan only what could be shown to a user. Frappe puts the full Python
		// traceback in `exc` on EVERY error response, including a deliberate
		// `frappe.throw`, so matching against the whole body discarded authored
		// validation messages too — a bad postal code read "Something went
		// wrong". A technical `_server_messages` is still caught downstream by
		// `isTechnicalMessage` on the extracted message itself.
		return TECHNICAL_MESSAGE_RE.test(exception);
	} catch {
		// Unparseable body: nothing to be precise about, so fall back to the
		// blunt scan rather than render whatever it happens to contain.
		return TECHNICAL_MESSAGE_RE.test(bodyText);
	}
};

export const isTechnicalMessage = (message) =>
	!!message && TECHNICAL_MESSAGE_RE.test(String(message));

const isSessionError = (status, bodyText) => {
	if (status === 401) return true;
	if (status !== 403) return false;
	return /CSRFTokenError|SessionStopped/i.test(bodyText || "");
};

// Build an Error whose .message is always safe to render to the user.
// The raw body and status are attached as non-enumerable properties so
// callers that want to log the full payload can reach for them, but
// JSON.stringify / accidental serialisation won't leak them.
export const buildError = (
	message,
	{ status = 0, raw = null, cause = null, field = null } = {}
) => {
	const err = new Error(message);
	Object.defineProperty(err, "userMessage", { value: message, enumerable: false });
	Object.defineProperty(err, "raw", { value: raw, enumerable: false });
	Object.defineProperty(err, "status", { value: status, enumerable: false });
	Object.defineProperty(err, "field", { value: field, enumerable: false });
	if (cause) Object.defineProperty(err, "cause", { value: cause, enumerable: false });
	return err;
};

export const friendlyError = (response, bodyText) => {
	const status = response.status;
	logger.error("API error", { status, raw: bodyText });

	if (isSessionError(status, bodyText)) {
		return buildError(MSG_SESSION, { status, raw: bodyText });
	}
	if (hasTechnicalException(bodyText)) {
		return buildError(MSG_GENERIC, { status, raw: bodyText });
	}
	const frappeMsg = extractFrappeMessage(bodyText);
	if (frappeMsg) {
		if (isTechnicalMessage(frappeMsg)) {
			return buildError(MSG_GENERIC, { status, raw: bodyText });
		}
		return buildError(frappeMsg, {
			status,
			raw: bodyText,
			field: extractFieldName(bodyText),
		});
	}
	return buildError(MSG_GENERIC, { status, raw: bodyText });
};

export const networkError = (cause) => {
	logger.error("Network error", cause);
	return buildError(MSG_NETWORK, { status: 0, cause });
};

const parseResponse = async (response) => {
	if (!response.ok) {
		const body = await response.text();
		throw friendlyError(response, body);
	}
	const data = await response.json();
	// Frappe occasionally returns HTTP 200 with an exception payload.
	if (data?.exc) {
		throw friendlyError(response, JSON.stringify(data));
	}
	return data.message;
};

export const baseCall = async (method, args = {}) => {
	let response;
	try {
		response = await fetch(`/api/method/${method}`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": getCsrfToken(),
				Accept: "application/json",
			},
			body: JSON.stringify(args),
			credentials: "same-origin",
		});
	} catch (cause) {
		throw networkError(cause);
	}

	return parseResponse(response);
};

export const getCall = async (method, params = {}) => {
	const filteredParams = Object.fromEntries(
		Object.entries(params).filter(([, v]) => v !== null && v !== undefined)
	);
	const query = new URLSearchParams(filteredParams).toString();
	const url = query ? `/api/method/${method}?${query}` : `/api/method/${method}`;

	let response;
	try {
		response = await fetch(url, {
			method: "GET",
			headers: {
				Accept: "application/json",
				"X-Frappe-CSRF-Token": getCsrfToken(),
			},
			credentials: "same-origin",
		});
	} catch (cause) {
		throw networkError(cause);
	}

	return parseResponse(response);
};
