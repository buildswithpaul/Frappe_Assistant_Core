/**
 * The host side of a personal page's frame (pageFrameDoc.js), shared by the chat panel and, built
 * as public/js/fac_page_frame_host.js, the fac-pages Desk page.
 *
 * The page's script has no login of its own; every call it makes arrives here as a message, and
 * only messages from that page's own frame are read. A read is sent as the user over HTTP GET with
 * no prompt: Frappe rolls back the database at the end of every GET request (frappe/app.py
 * after_request commits only for POST, PUT and DELETE), so even a method that writes keeps
 * nothing, unless it commits itself, which FAC's own API rules forbid. A change is sent as POST
 * only after the user allows it in plain words.
 */
import { __ } from "@/utils/i18n";

import { PAGE_FRAME_SANDBOX, makeNonce, pageFrameSrcdoc } from "./pageFrameDoc";

// Methods that change data, asked about before any GET is tried.
export const PAGE_WRITE_METHODS = new Set([
	"frappe.client.insert",
	"frappe.client.insert_many",
	"frappe.client.save",
	"frappe.client.set_value",
	"frappe.client.submit",
	"frappe.client.cancel",
	"frappe.client.delete",
	"frappe.client.rename_doc",
	"frappe.client.bulk_update",
	"frappe.client.attach_file",
	"frappe.desk.form.save.savedocs",
	"frappe.desk.form.save.cancel",
	"run_doc_method",
]);

const METHOD_RE = /^[A-Za-z0-9_][A-Za-z0-9_.]{0,139}$/;
const MAX_ARGS_BYTES = 1024 * 1024;
const MAX_ERRORS = 20;
const MAX_TEXT = 500;
const MAX_SNAPSHOT_BYTES = 5 * 1024 * 1024;
const RESULT_TIMEOUT_MS = 15000;
// A print or a picture waits for the script to run and its calls to come back, this long at most,
// then this long with nothing in flight, so the figures it fetched are drawn.
const IDLE_TIMEOUT_MS = 8000;
const IDLE_QUIET_MS = 300;

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

const isPlainObject = (value) =>
	value !== null && typeof value === "object" && Object.getPrototypeOf(value) === Object.prototype;

/** A call message from the frame as {id, method, args, type}, or null when it is malformed. */
export function readCall(data) {
	if (!Number.isInteger(data.id) || data.id < 1) return null;
	if (typeof data.method !== "string" || !METHOD_RE.test(data.method)) return null;
	const args = data.args === undefined ? {} : data.args;
	if (!isPlainObject(args)) return null;
	let size;
	try {
		size = JSON.stringify(args).length;
	} catch {
		return null;
	}
	if (size > MAX_ARGS_BYTES) return null;
	if (data.type !== undefined && data.type !== "GET" && data.type !== "POST") return null;
	return { id: data.id, method: data.method, args, type: data.type };
}

const short = (value) => {
	const text = value !== null && typeof value === "object" ? JSON.stringify(value) : String(value ?? "");
	return text.length > 60 ? `${text.slice(0, 57)}…` : text;
};

const parseDoc = (doc) => {
	if (typeof doc !== "string") return isPlainObject(doc) ? doc : {};
	try {
		const parsed = JSON.parse(doc);
		return isPlainObject(parsed) ? parsed : {};
	} catch {
		return {};
	}
};

/** What a change does, in the words the user is asked to allow it in. */
export function describePageWrite(method, args = {}) {
	const doc = parseDoc(args.doc);
	const doctype = short(args.doctype || doc.doctype);
	const name = short(args.name || doc.name);
	switch (method) {
		case "frappe.client.set_value": {
			const fields = isPlainObject(args.fieldname)
				? Object.entries(args.fieldname)
				: [[args.fieldname, args.value]];
			const changes = fields
				.slice(0, 3)
				.map(([field, value]) => `${short(field)} → ${short(value)}`)
				.join(", ");
			const more = fields.length > 3 ? __(" and {0} more", [fields.length - 3]) : "";
			return __("This page wants to update {0} {1}: {2}{3}.", [doctype, name, changes, more]);
		}
		case "frappe.client.insert":
			return __("This page wants to create a new {0}.", [doctype]);
		case "frappe.client.delete":
			return __("This page wants to delete {0} {1}.", [doctype, name]);
		case "frappe.client.save":
			return __("This page wants to save changes to {0} {1}.", [doctype, name]);
		case "frappe.client.submit":
			return __("This page wants to submit {0} {1}.", [doctype, name]);
		case "frappe.client.cancel":
			return __("This page wants to cancel {0} {1}.", [doctype, name]);
		default:
			return __("This page wants to run {0}, which can change data.", [short(method)]);
	}
}

// A method that refuses GET answers 403 (frappe.handler.is_valid_http_method) or 405.
const refusedGet = (error) => error?.status === 403 || error?.status === 405;

const errorReply = (error) => ({
	message: String(error?.userMessage || error?.message || __("The request failed")).slice(0, MAX_TEXT),
	status: Number(error?.status) || 0,
});

/**
 * Build a personal page's frame and serve its bridge.
 *
 * @param {object} options
 * @param {{title?: string, html?: string, style?: string, script?: string}} options.page get_page's response
 * @param {string} options.kitCss the mockup kit
 * @param {string} options.user the session user
 * @param {string} [options.origin] the site origin; the window's own by default
 * @param {string} [options.version] the build version, so a rebuilt bundle is refetched
 * @param {{get: (method: string, args: object) => Promise, post: (method: string, args: object) => Promise}} options.transport
 *   sends a call as the user and resolves with its message
 * @param {(description: string) => Promise<boolean>} options.askWrite asks the user to allow a change
 * @param {(message: string) => void} [options.onError] a script error or a failed call
 * @param {(name: string) => void} [options.onUnsupported] a Desk member the script reached for
 * @param {(height: number) => void} [options.onHeight] the page's height, as it changes
 * @param {() => void} [options.onReady] the script has run
 * @returns {{element: HTMLIFrameElement, errors: string[], snapshot: Function, dispose: Function}}
 */
export function createPageFrame({
	page,
	kitCss,
	user,
	origin = window.location.origin,
	version = "",
	transport,
	askWrite,
	onError,
	onUnsupported,
	onHeight,
	onReady,
}) {
	const element = document.createElement("iframe");
	element.setAttribute("sandbox", PAGE_FRAME_SANDBOX);
	element.setAttribute("referrerpolicy", "no-referrer");
	element.setAttribute("title", page.title || __("Page"));
	element.className = "fac-page-sandbox";
	element.srcdoc = pageFrameSrcdoc({
		html: page.html,
		style: page.style,
		script: page.script,
		kitCss,
		user,
		origin,
		nonce: makeNonce(),
		version,
	});

	const errors = [];
	const results = new Map();
	let nextId = 0;
	let disposed = false;
	let ready = false;
	let inFlight = 0;
	const idleWaiters = new Set();

	function checkIdle() {
		if (!ready || inFlight > 0) return;
		for (const waiter of idleWaiters) waiter.arm();
	}

	/** Resolves once the script has run and no call has been in flight for a moment, or on timeout. */
	function whenIdle() {
		return new Promise((resolve) => {
			let quiet = null;
			const waiter = {
				arm() {
					clearTimeout(quiet);
					quiet = setTimeout(() => {
						if (ready && inFlight === 0) finish();
					}, IDLE_QUIET_MS);
				},
			};
			const cap = setTimeout(() => finish(), IDLE_TIMEOUT_MS);
			function finish() {
				clearTimeout(quiet);
				clearTimeout(cap);
				idleWaiters.delete(waiter);
				resolve();
			}
			idleWaiters.add(waiter);
			checkIdle();
		});
	}

	// The page's own window: the outer frame's one child. Anything else posting here is ignored.
	const pageWindow = () => element.contentWindow?.frames?.[0] || null;
	const toPage = (message) => {
		const target = pageWindow();
		// An opaque origin can only be addressed as "*"; the target is this page's frame itself.
		if (target && !disposed) target.postMessage({ fac_page: 1, ...message }, "*");
	};

	function noteError(message) {
		const text = String(message || "").slice(0, MAX_TEXT);
		if (errors.length < MAX_ERRORS) errors.push(text);
		onError?.(text);
	}

	async function write(method, args) {
		if (!(await askWrite(describePageWrite(method, args)))) {
			throw Object.assign(new Error(__("The user did not allow this change.")), { status: 403 });
		}
		return transport.post(method, args);
	}

	async function serve({ method, args, type }) {
		if (type === "POST" || PAGE_WRITE_METHODS.has(method)) return write(method, args);
		try {
			return await transport.get(method, args);
		} catch (error) {
			// A call that named no type may be a change Frappe will only take as POST: ask, as for one.
			if (type === undefined && refusedGet(error)) return write(method, args);
			throw error;
		}
	}

	async function onCall(call) {
		inFlight++;
		try {
			const message = await serve(call);
			toPage({ op: "reply", id: call.id, ok: true, message: message === undefined ? null : message });
		} catch (error) {
			const reply = errorReply(error);
			noteError(__("{0} failed: {1}", [call.method, reply.message]));
			toPage({ op: "reply", id: call.id, ok: false, error: reply });
		} finally {
			inFlight--;
			checkIdle();
		}
	}

	function settle(id, value) {
		const pending = results.get(id);
		if (!pending) return;
		results.delete(id);
		clearTimeout(pending.timer);
		if (value instanceof Error) pending.reject(value);
		else pending.resolve(value);
	}

	function onMessage(event) {
		const source = pageWindow();
		if (!source || event.source !== source) return;
		const data = event.data;
		if (!isPlainObject(data) || data.fac_page !== 1) return;
		switch (data.op) {
			case "call": {
				const call = readCall(data);
				if (call) onCall(call);
				else if (Number.isInteger(data.id)) {
					toPage({ op: "reply", id: data.id, ok: false, error: { message: __("This request is not allowed."), status: 0 } });
				}
				return;
			}
			case "error":
				if (typeof data.message === "string") noteError(data.message);
				return;
			case "unsupported":
				if (typeof data.name === "string") onUnsupported?.(data.name.slice(0, 100));
				return;
			case "height":
				if (Number.isFinite(data.height) && data.height >= 0) onHeight?.(Math.min(data.height, 100000));
				return;
			case "ready":
				ready = true;
				checkIdle();
				onReady?.();
				return;
			case "snapshot_result": {
				const ok = typeof data.html === "string" && data.html.length <= MAX_SNAPSHOT_BYTES;
				if (!ok) return settle(data.id, new Error(__("The page sent nothing to print.")));
				return settle(data.id, { html: data.html, wide: data.wide === true });
			}
			default:
		}
	}

	function request(op, extra = {}) {
		const id = ++nextId;
		return new Promise((resolve, reject) => {
			const timer = setTimeout(() => {
				results.delete(id);
				reject(new Error(__("The page did not answer.")));
			}, RESULT_TIMEOUT_MS);
			results.set(id, { resolve, reject, timer });
			toPage({ op, id, ...extra });
		});
	}

	window.addEventListener("message", onMessage);

	return {
		element,
		errors,
		/** The page's rendered markup, for Download PDF and FACO's picture: {html, wide}. */
		snapshot: async () => {
			await whenIdle();
			return request("snapshot");
		},
		dispose() {
			disposed = true;
			window.removeEventListener("message", onMessage);
			for (const id of [...results.keys()]) settle(id, new Error(__("The page was closed.")));
		},
	};
}
