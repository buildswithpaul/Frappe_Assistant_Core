/**
 * The host side of a personal page's frame (pageFrameDoc.js), shared by the chat panel and, built
 * as public/js/fac_page_frame_host.js, the fac-pages Desk page.
 *
 * The page's script has no login of its own; every call it makes arrives here as a message, and
 * only messages from that page's own frame are read. Only the reads in PAGE_READ_METHODS run
 * without asking, and always over HTTP GET. Frappe rolls the database back at the end of a GET
 * request (frappe/app.py after_request commits only for POST, PUT and DELETE), but that stops
 * database writes, not side effects such as a queued job, an email or an outbound request. So no
 * other method, whatever its name or HTTP method, runs until the user allows it, and what they are
 * shown is exactly what is then sent.
 */
import { __ } from "@/utils/i18n";

import { PAGE_FRAME_SANDBOX, makeNonce, pageFrameSrcdoc } from "./pageFrameDoc";

// The reads a page runs without asking: Frappe's own read endpoints, which check the user's
// permission and change nothing. The chat's stand-in frappe uses get_list, get_value and get.
export const PAGE_READ_METHODS = new Set([
	"frappe.client.get",
	"frappe.client.get_list",
	"frappe.client.get_count",
	"frappe.client.get_value",
	"frappe.client.get_single_value",
	"frappe.desk.reportview.get",
	"frappe.desk.reportview.get_count",
	"frappe.desk.query_report.run",
	"frappe.desk.form.load.getdoc",
]);

// Frappe's record writes: described field by field and allowed one at a time, never trusted for
// the page, since the next call may change other records or fields.
const RECORD_WRITES = new Set([
	"frappe.client.set_value",
	"frappe.client.insert",
	"frappe.client.save",
	"frappe.client.submit",
	"frappe.client.cancel",
	"frappe.client.delete",
]);

// Methods the user allowed for a page this session, as "page name\0method".
const pageTrust = new Set();

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

const MAX_FIELDS = 8;

const short = (value) => {
	if (Array.isArray(value)) return value.length === 1 ? __("1 row") : __("{0} rows", [value.length]);
	const text = value !== null && typeof value === "object" ? JSON.stringify(value) : String(value ?? "");
	return text.length > 80 ? `${text.slice(0, 77)}…` : text;
};

// The document a write carries, which may come as a JSON string.
function parseDoc(doc) {
	if (isPlainObject(doc)) return doc;
	if (typeof doc !== "string") return null;
	try {
		const parsed = JSON.parse(doc);
		return isPlainObject(parsed) ? parsed : null;
	} catch {
		return null;
	}
}

// Keys every document carries that say nothing about what changes.
const DOC_KEYS = new Set(["doctype", "name", "__islocal", "__unsaved", "owner", "creation", "modified", "modified_by"]);

function fieldList(entries) {
	const fields = entries.map(([field, value]) => [short(field), short(value)]);
	if (fields.length <= MAX_FIELDS) return fields;
	return [...fields.slice(0, MAX_FIELDS), [__("and {0} more", [fields.length - MAX_FIELDS]), ""]];
}

const refuse = () => Object.assign(new Error(__("This request is not allowed.")), { status: 0, refused: true });

/**
 * What the user is asked to allow, read from the exact payload that will be sent:
 * {message, fields: [[name, value]], trustable}. Throws when a write names a record two ways.
 */
export function describePageRequest(method, payload = {}) {
	if (["frappe.client.insert", "frappe.client.save", "frappe.client.submit"].includes(method)) {
		const doc = parseDoc(payload.doc);
		// The record is the one in doc; a top-level doctype or name that says otherwise is refused.
		if (!doc || typeof doc.doctype !== "string" || !doc.doctype) throw refuse();
		if (payload.doctype !== undefined && payload.doctype !== doc.doctype) throw refuse();
		if (payload.name !== undefined && payload.name !== doc.name) throw refuse();
		const fields = fieldList(Object.entries(doc).filter(([key]) => !DOC_KEYS.has(key)));
		const doctype = short(doc.doctype);
		const name = short(doc.name);
		const message = {
			"frappe.client.insert": __("This page wants to create a new {0}.", [doctype]),
			"frappe.client.save": __("This page wants to save {0} {1}.", [doctype, name]),
			"frappe.client.submit": __("This page wants to submit {0} {1}.", [doctype, name]),
		}[method];
		return { message, fields: method === "frappe.client.submit" ? [] : fields, trustable: false };
	}
	if (method === "frappe.client.set_value") {
		const entries = isPlainObject(payload.fieldname)
			? Object.entries(payload.fieldname)
			: [[payload.fieldname, payload.value]];
		return {
			message: __("This page wants to update {0} {1}.", [short(payload.doctype), short(payload.name)]),
			fields: fieldList(entries),
			trustable: false,
		};
	}
	if (method === "frappe.client.cancel" || method === "frappe.client.delete") {
		const verb = method === "frappe.client.cancel" ? __("cancel") : __("delete");
		return {
			message: __("This page wants to {0} {1} {2}.", [verb, short(payload.doctype), short(payload.name)]),
			fields: [],
			trustable: false,
		};
	}
	return {
		message: __("This page wants to run {0}.", [short(method)]),
		fields: fieldList(Object.entries(payload)),
		trustable: true,
	};
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
 * @param {string} options.pageName the FAC Page record name, which "Allow for this page" is scoped to
 * @param {(request: {message: string, fields: Array, trustable: boolean}) => Promise<"once"|"page"|false>} options.askUser
 *   asks the user to allow a call; "page" allows that method for this page for the session
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
	pageName = "",
	transport,
	askUser,
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

	const trustKey = (method) => `${pageName}\u0000${method}`;

	// One question per method at a time, so a second call waits for the first answer, which may
	// have allowed the method for this page.
	const asking = new Map();

	async function approve(method, payload) {
		const request = describePageRequest(method, payload);
		const earlier = asking.get(method);
		const turn = (async () => {
			await earlier?.catch(() => {});
			if (request.trustable && pageName && pageTrust.has(trustKey(method))) return;
			const answer = await askUser(request);
			if (!answer) throw Object.assign(new Error(__("The user did not allow this.")), { status: 403 });
			if (answer === "page" && request.trustable && pageName) pageTrust.add(trustKey(method));
		})();
		asking.set(method, turn);
		try {
			await turn;
		} finally {
			if (asking.get(method) === turn) asking.delete(method);
		}
	}

	async function serve({ method, args, type }) {
		// A private copy: the payload the user is shown is the payload sent, whatever the page does.
		const payload = JSON.parse(JSON.stringify(args));
		if (PAGE_READ_METHODS.has(method)) return transport.get(method, payload);
		await approve(method, payload);
		if (RECORD_WRITES.has(method) || type === "POST") return transport.post(method, payload);
		if (type === "GET") return transport.get(method, payload);
		try {
			return await transport.get(method, payload);
		} catch (error) {
			// Allowed already; a method Frappe takes only as POST is sent so, with the same payload.
			if (refusedGet(error)) return transport.post(method, payload);
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
