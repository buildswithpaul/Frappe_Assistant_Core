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
import {
	DOC_REPLACING_WRITES,
	RECORD_WRITES,
	describePageRequest,
	fitsCurrentDoc,
	isMethodName,
	isPlainObject,
	asFieldUpdate,
	mayTrustForPage,
	mergeWithCurrent,
	normalisePayload,
	refusal,
} from "./pageRequestPrompt";

export { describePageRequest } from "./pageRequestPrompt";
export { fetchTransport, queryArgs } from "./pageFetchTransport";

// The reads a page runs without asking: Frappe's own read endpoints, which check the user's
// permission. The chat's stand-in frappe uses get_list, get_value and get. query_report.run runs a
// report's own code and getdoc a controller's onload; both are what the user can already run from
// Desk, and GET rolls back any database write they make.
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

// Per page, in memory only: the content the answers below were given for, the methods the user
// allowed for it, and the methods they refused. A new version of the page starts afresh.
const pageStates = new Map();

function pageState(pageName, content) {
	const state = pageStates.get(pageName);
	if (state && state.content === content) return state;
	const fresh = { content, trusted: new Set(), denied: new Set(), denials: 0 };
	if (pageName) pageStates.set(pageName, fresh);
	return fresh;
}

// At most this many calls wait for the user at once; the rest are refused, so a page cannot bury
// one change in a run of harmless questions. Reads run this many at a time.
const MAX_WAITING_ASKS = 5;
const MAX_READS_AT_ONCE = 8;
const MAX_QUEUED_READS = 200;
// After this many refusals on one version of a page, it may only read.
const MAX_DENIALS = 3;
// Answers whether a dotless name is a Server Script API method the site has not remapped.
const PAGE_API_CHECK = "frappe_assistant_core.api.fac_page.is_page_api_method";

const MAX_ARGS_BYTES = 1024 * 1024;
const MAX_ERRORS = 20;
const MAX_TEXT = 500;
const MAX_SNAPSHOT_BYTES = 5 * 1024 * 1024;
const MAX_IMAGE_BYTES = 15 * 1024 * 1024;
const MAX_PAGE_TEXT = 8000;
const MAX_DIMENSION = 20000;
const RESULT_TIMEOUT_MS = 15000;
// A print or a picture waits for the script to run and its calls to come back, this long at most,
// then this long with nothing in flight, so the figures it fetched are drawn.
const IDLE_TIMEOUT_MS = 8000;
const IDLE_QUIET_MS = 300;

/** A call message from the frame as {id, method, args, type}, or null when it is malformed. */
export function readCall(data) {
	if (!Number.isInteger(data.id) || data.id < 1) return null;
	// A plain dotted path only: no "/", "?", "%" or "..", which could reach another endpoint.
	if (!isMethodName(data.method)) return null;
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

// A JPEG from the frame: an ArrayBuffer of a sensible size that starts as a JPEG does.
function isJpeg(buffer) {
	if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < 4 || buffer.byteLength > MAX_IMAGE_BYTES) return false;
	const head = new Uint8Array(buffer, 0, 3);
	return head[0] === 0xff && head[1] === 0xd8 && head[2] === 0xff;
}

const dimension = (value) => Math.min(Math.max(Math.round(Number(value) || 0), 0), MAX_DIMENSION);

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
 * @param {(request: object) => Promise<"once"|"page"|false>} options.askUser asks the user to allow
 *   a call (describePageRequest's request); "page" allows that method for this version of the page
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

	const state = pageState(pageName, JSON.stringify([page.html || "", page.style || "", page.script || ""]));
	let waitingAsks = 0;

	// One question per method at a time, so a second call waits for the first answer.
	const asking = new Map();

	const denied = () => Object.assign(new Error(__("The user did not allow this.")), { status: 403 });

	// The document as it is now, read as the user, so a save or submit can show what it changes. A
	// failed read refuses the write.
	async function currentDoc(doc) {
		try {
			const current = await transport.get("frappe.client.get", { doctype: doc.doctype, name: doc.name });
			if (isPlainObject(current)) return current;
		} catch {
			// refused below
		}
		throw refusal();
	}

	// Whether the site says this name is a Server Script API method; anything else is never trusted.
	async function siteAllowsTrust(method) {
		if (!mayTrustForPage(method)) return false;
		try {
			return (await transport.get(PAGE_API_CHECK, { method })) === true;
		} catch {
			return false;
		}
	}

	// Resolves with the exact call to send once the user allows it: {method, payload}, or {done}
	// when there is nothing to send.
	async function approve(method, payload) {
		if (state.denied.has(method) || state.denials >= MAX_DENIALS) throw denied();
		if (waitingAsks >= MAX_WAITING_ASKS) {
			throw Object.assign(new Error(__("Too many requests are waiting for the user.")), { status: 429 });
		}
		waitingAsks++;
		const earlier = asking.get(method);
		const turn = (async () => {
			await earlier?.catch(() => {});
			if (state.denied.has(method) || state.denials >= MAX_DENIALS) throw denied();
			let current = null;
			let call = { method, payload };
			if (DOC_REPLACING_WRITES.has(method)) {
				current = await currentDoc(payload.doc);
				if (!fitsCurrentDoc(method, payload.doc, current)) throw refusal();
				const merged = mergeWithCurrent(payload, current);
				// A save of top-level fields only writes exactly those fields, nothing else on the record.
				const update = method === "frappe.client.save" ? asFieldUpdate(merged, current) : null;
				if (update && !Object.keys(update.fieldname).length) return { done: current };
				call = update ? { method: "frappe.client.set_value", payload: update } : { method, payload: merged };
			}
			if (state.trusted.has(method)) return call;
			const request = describePageRequest(call.method, call.payload, current, await siteAllowsTrust(method));
			const answer = await askUser(request);
			if (!answer) {
				state.denied.add(method);
				state.denials++;
				throw denied();
			}
			if (answer === "page" && request.trustable) state.trusted.add(method);
			return call;
		})();
		asking.set(method, turn);
		try {
			return await turn;
		} finally {
			waitingAsks--;
			if (asking.get(method) === turn) asking.delete(method);
		}
	}

	let readsRunning = 0;
	const readQueue = [];
	async function read(method, payload) {
		if (readsRunning >= MAX_READS_AT_ONCE) {
			if (readQueue.length >= MAX_QUEUED_READS) {
				throw Object.assign(new Error(__("Too many reads are waiting.")), { status: 429 });
			}
			await new Promise((resolve) => readQueue.push(resolve));
		}
		readsRunning++;
		try {
			return await transport.get(method, payload);
		} finally {
			readsRunning--;
			readQueue.shift()?.();
		}
	}

	async function serve({ method, args, type }) {
		// A private copy, read the way Frappe will read it: the payload the user is shown is the
		// payload sent, whatever the page does next.
		const copy = JSON.parse(JSON.stringify(args));
		if (PAGE_READ_METHODS.has(method)) return read(method, copy);
		const normalised = normalisePayload(method, copy);
		if (!normalised) throw refusal();
		const call = await approve(method, normalised);
		if (call.done) return call.done;
		if (call.method !== method) return transport.post(call.method, call.payload);
		const { payload } = call;
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
			case "capture_result": {
				const text = typeof data.text === "string" ? data.text.slice(0, MAX_PAGE_TEXT) : "";
				if (typeof data.error === "string") {
					return settle(
						data.id,
						Object.assign(new Error(__("This browser can't capture the page.")), {
							text,
							detail: data.error.slice(0, MAX_TEXT),
						}),
					);
				}
				if (!isJpeg(data.buffer) || data.type !== "image/jpeg") {
					return settle(data.id, Object.assign(new Error(__("The page sent no picture.")), { text }));
				}
				return settle(data.id, {
					blob: new Blob([data.buffer], { type: "image/jpeg" }),
					width: dimension(data.width),
					height: dimension(data.height),
					text,
				});
			}
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
		/**
		 * FACO's picture, drawn inside the frame: {blob, width, height, text}. Rejects with an error
		 * carrying `text`, the page's visible text, when the frame cannot draw it.
		 */
		capture: async ({ scale = 1, quality = 80 } = {}) => {
			await whenIdle();
			return request("capture", { scale, quality });
		},
		/** The page's rendered markup, for Download PDF: {html, wide}. */
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
