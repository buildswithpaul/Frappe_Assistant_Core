/**
 * What the user is asked to allow when a personal page calls anything beyond Frappe's own reads
 * (pageFrameHost.js). Every word comes from the exact payload that is then sent, so the prompt
 * hides nothing: every field, every value in full, every child row.
 */
import { __ } from "@/utils/i18n";

// Frappe's record writes: described field by field and allowed one call at a time.
export const RECORD_WRITES = new Set([
	"frappe.client.set_value",
	"frappe.client.insert",
	"frappe.client.save",
	"frappe.client.submit",
	"frappe.client.cancel",
	"frappe.client.delete",
]);

// Writes that rebuild a whole document from the payload (frappe/client.py save and submit call
// frappe.get_doc(dict), and db_update writes every column, so a key the payload leaves out is
// written as null). The host reads the current record first and sends it merged with the page's
// changes, so a field the page does not mention keeps its value.
export const DOC_REPLACING_WRITES = new Set(["frappe.client.save", "frappe.client.submit"]);

// Bidirectional overrides, zero-width and other invisible characters, which can make a prompt
// read differently from what is sent.
const HIDDEN_CHARS = /[\u00AD\u061C\u180E\u200B-\u200F\u202A-\u202E\u2060-\u2064\u2066-\u2069\uFEFF]/g;

// The only keys left out of a prompt: client-side flags, and the timestamp Frappe checks itself.
const OMITTED_KEYS = new Set(["__islocal", "__unsaved", "modified"]);
// A document's own doctype and name are in the prompt's sentence, not its field list.
const NAMING_KEYS = new Set(["doctype", "name", "__newname"]);
// Keys a page may not set at all: where a record hangs.
const PARENT_KEYS = ["parent", "parenttype", "parentfield"];
// Keys the server owns: absent on insert, and on save or submit equal to the record's own.
const SERVER_KEYS = ["owner", "creation", "modified_by"];
// Keys set_value may not set, which frappe/client.py checks only for a single field name.
const SET_VALUE_REFUSED = new Set(["name", "doctype", "docstatus", "idx", "modified", ...SERVER_KEYS, ...PARENT_KEYS]);

const METHOD_RE = /^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$/;
const SERVER_SCRIPT_API_RE = /^[A-Za-z0-9_]+$/;

/** Whether a method name is a plain dotted Python path, the only kind a page may call. */
export const isMethodName = (method) => typeof method === "string" && method.length <= 140 && METHOD_RE.test(method);

export const isPlainObject = (value) =>
	value !== null && typeof value === "object" && Object.getPrototypeOf(value) === Object.prototype;

/** A refused request: the host replies with this error and asks nothing. */
export const refusal = () => Object.assign(new Error(__("This request is not allowed.")), { status: 0, refused: true });

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

const isRecordName = (name) => (typeof name === "string" && name !== "") || Number.isInteger(name);

// A page's own document: no underscore key but the ones allowed here, no parent keys, and on
// insert none of the server's own keys.
function docKeysAllowed(method, doc) {
	for (const key of Object.keys(doc)) {
		if (key.startsWith("_") && !["__islocal", "__unsaved"].includes(key) && !(key === "__newname" && method === "frappe.client.insert")) {
			return false;
		}
	}
	if (PARENT_KEYS.some((key) => key in doc)) return false;
	if (method === "frappe.client.insert" && SERVER_KEYS.some((key) => key in doc)) return false;
	// Inserting and saving only make drafts; submitting and cancelling are their own calls.
	if (doc.docstatus !== undefined && doc.docstatus !== 0) return false;
	for (const value of Object.values(doc)) {
		if (!Array.isArray(value)) continue;
		for (const row of value) {
			if (isPlainObject(row) && Object.keys(row).some((key) => key.startsWith("_") && !["__islocal", "__unsaved"].includes(key))) {
				return false;
			}
		}
	}
	return true;
}

/**
 * The payload as Frappe will read it, so what is described is what runs. set_value's fieldname
 * becomes the object Frappe would build (frappe/client.py: a falsy value makes a string fieldname
 * JSON, or a field set to ""); a doc given as a JSON string becomes an object. Returns null for a
 * payload Frappe could not read as described, or one a page may not send.
 */
export function normalisePayload(method, payload) {
	if (method === "frappe.client.set_value") {
		const { fieldname, value, ...rest } = payload;
		let values;
		if (isPlainObject(fieldname)) values = fieldname;
		else if (typeof fieldname !== "string" || !fieldname) return null;
		else if (value) values = { [fieldname]: value };
		else {
			try {
				values = JSON.parse(fieldname);
			} catch {
				values = { [fieldname]: "" };
			}
		}
		if (!isPlainObject(values) || !Object.keys(values).length) return null;
		if (Object.keys(values).some((key) => key.startsWith("_") || SET_VALUE_REFUSED.has(key))) return null;
		return { ...rest, fieldname: values };
	}
	if (["frappe.client.insert", "frappe.client.save", "frappe.client.submit"].includes(method)) {
		const doc = parseDoc(payload.doc);
		// The record is the one in doc; a top-level doctype or name that says otherwise is refused.
		if (!doc || typeof doc.doctype !== "string" || !doc.doctype) return null;
		if (payload.doctype !== undefined && payload.doctype !== doc.doctype) return null;
		if (payload.name !== undefined && payload.name !== doc.name) return null;
		if (DOC_REPLACING_WRITES.has(method) && !isRecordName(doc.name)) return null;
		if (!docKeysAllowed(method, doc)) return null;
		return { ...payload, doc };
	}
	return payload;
}

const same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

/**
 * Whether a save or submit fits the record as it is now: a save keeps its docstatus, a submit
 * starts from a draft, and the server's own keys, if sent, are the record's own.
 *
 * @param {object} doc the page's document
 * @param {object} current the record read just before asking
 */
export function fitsCurrentDoc(method, doc, current) {
	if (!DOC_REPLACING_WRITES.has(method)) return true;
	if (method === "frappe.client.save" && (doc.docstatus ?? current.docstatus ?? 0) !== (current.docstatus ?? 0)) return false;
	if (method === "frappe.client.submit" && (current.docstatus ?? 0) !== 0) return false;
	return SERVER_KEYS.every((key) => !(key in doc) || same(doc[key], current[key]));
}

/**
 * A save that changes only top-level fields, as the set_value of exactly those fields, so nothing
 * else on the record is written. Null when it changes a child table, which only a whole-record
 * save can do. An empty fieldname means nothing changes.
 *
 * @param {object} merged the merged save payload (mergeWithCurrent)
 * @param {object} current the record read just before asking
 */
export function asFieldUpdate(merged, current) {
	const changed = shownKeys(merged.doc).filter((key) => !same(merged.doc[key], current[key]));
	if (changed.some((key) => Array.isArray(merged.doc[key]) || Array.isArray(current[key]))) return null;
	return {
		doctype: merged.doc.doctype,
		name: merged.doc.name,
		fieldname: Object.fromEntries(changed.map((key) => [key, merged.doc[key]])),
	};
}

/**
 * What a save or submit sends: the record as it is now, with the page's changes over it. Used for a
 * submit, and for a save that changes a child table. Edge: a field at a permlevel the user can
 * write but not read is missing from the record as read (frappe.client.get drops it), so a merged
 * save writes it as null; validate_higher_perm_levels restores only fields the user cannot write.
 */
export function mergeWithCurrent(payload, current) {
	const { __islocal, __unsaved, ...doc } = payload.doc;
	return { ...payload, doc: { ...current, ...doc } };
}

/** Builds display text with hidden characters removed, remembering whether any were. */
function textMaker() {
	const state = { hidden: false };
	const text = (value) => {
		const raw = value !== null && typeof value === "object" ? JSON.stringify(value) : String(value ?? "");
		const shown = raw.replace(HIDDEN_CHARS, "");
		if (shown !== raw) state.hidden = true;
		return shown;
	};
	return { text, state };
}

// A child table's rows, each as its fields; only each row's position and client flags are left out.
const rowsOf = (value, text) =>
	value.map((row) =>
		isPlainObject(row)
			? Object.entries(row)
					.filter(([key]) => key !== "idx" && !OMITTED_KEYS.has(key))
					.map(([name, cell]) => ({ name: text(name), value: text(cell) }))
			: [{ name: "", value: text(row) }],
	);

function field(name, value, text, extra = {}) {
	if (Array.isArray(value)) return { name: text(name), value: "", rows: rowsOf(value, text), ...extra };
	return { name: text(name), value: text(value), ...extra };
}

const shownKeys = (doc) => Object.keys(doc).filter((key) => !OMITTED_KEYS.has(key) && !NAMING_KEYS.has(key));

// Every field a new document sets.
const insertFields = (doc, text) => shownKeys(doc).map((key) => field(key, doc[key], text));

// What a merged save or submit changes, before and after. Everything else is sent as it is now.
function changedFields(merged, current, text) {
	return shownKeys(merged)
		.filter((key) => !same(merged[key], current[key]))
		.map((key) => {
			const value = merged[key];
			const before = current[key];
			if (Array.isArray(value)) return field(key, value, text, { status: "changed", beforeRows: Array.isArray(before) ? before.length : 0 });
			const blank = value === null || value === "" || value === undefined;
			return field(key, value, text, { status: blank ? "blanked" : "changed", before: text(before ?? "") });
		});
}

/**
 * The prompt for a call: {message, note, fields, trustable, hiddenChars}.
 *
 * @param {string} method
 * @param {object} payload the normalised payload, exactly as it will be sent (for save and submit,
 *   already merged with the current record)
 * @param {object} [current] the record as it is now, for save and submit
 * @param {boolean} [mayTrust] whether this method may be allowed for the page (pageFrameHost asks
 *   the site first)
 */
export function describePageRequest(method, payload = {}, current = null, mayTrust = false) {
	const { text, state } = textMaker();
	let request;
	if (method === "frappe.client.set_value") {
		// With the record as it is now (a page's save sent as set_value), each field shows before and after.
		const fields = Object.entries(payload.fieldname || {}).map(([key, value]) =>
			current ? field(key, value, text, { before: text(current[key] ?? ""), status: value === "" || value === null ? "blanked" : "changed" }) : field(key, value, text),
		);
		request = {
			message: __("This page wants to change these fields on {0} {1}.", [text(payload.doctype), text(payload.name)]),
			fields,
		};
	} else if (method === "frappe.client.insert") {
		const name = payload.doc.__newname ?? payload.doc.name;
		request = {
			message: name
				? __("This page wants to create a new {0} named {1} with these fields.", [text(payload.doc.doctype), text(name)])
				: __("This page wants to create a new {0} with these fields.", [text(payload.doc.doctype)]),
			fields: insertFields(payload.doc, text),
		};
	} else if (method === "frappe.client.save") {
		request = {
			message: __("This page wants to save {0} {1}. These fields change; every other field keeps its current value.", [
				text(payload.doc.doctype),
				text(payload.doc.name),
			]),
			fields: changedFields(payload.doc, current, text),
		};
	} else if (method === "frappe.client.submit") {
		request = {
			message: __(
				"This page wants to submit {0} {1}. These fields change; every other field keeps its current value. Submitting can't be undone.",
				[text(payload.doc.doctype), text(payload.doc.name)],
			),
			fields: changedFields(payload.doc, current, text),
		};
	} else if (method === "frappe.client.cancel") {
		request = { message: __("This page wants to cancel {0} {1}.", [text(payload.doctype), text(payload.name)]), fields: [] };
	} else if (method === "frappe.client.delete") {
		request = { message: __("This page wants to delete {0} {1}.", [text(payload.doctype), text(payload.name)]), fields: [] };
	} else {
		request = {
			message: __("This page wants to run {0} with these values.", [text(method)]),
			fields: Object.entries(payload).map(([key, value]) => field(key, value, text)),
		};
	}
	const trustable = mayTrust && mayTrustForPage(method);
	return {
		...request,
		note: trustable ? __("Allow for this page lets this version of the page run {0} again without asking.", [text(method)]) : "",
		trustable,
		hiddenChars: state.hidden,
	};
}

// Dotless names Frappe resolves to its own handler (frappe/handler.py get_attr), not to a Server
// Script: they are never a page's own API.
const FRAPPE_HANDLER_COMMANDS = new Set([
	"logout",
	"web_logout",
	"uploadfile",
	"upload_file",
	"download_file",
	"run_doc_method",
	"runserverobj",
	"run_custom_method",
	"version",
	"ping",
]);

/**
 * Whether "Allow for this page" may be offered: only for a method with no dot in its name that is
 * not one of Frappe's own handler commands, which could be a Server Script API method, the kind
 * FACO writes. The host also asks the site whether it is one (is_page_api_method). Any dotted
 * method (frappe.*, erpnext.*, any app's module, savedocs, insert_many, bulk_update, rename_doc,
 * delete_items, apply_workflow), run_doc_method and every record write is allowed one call at a
 * time, described in full.
 */
export const mayTrustForPage = (method) =>
	SERVER_SCRIPT_API_RE.test(method) && !FRAPPE_HANDLER_COMMANDS.has(method) && !RECORD_WRITES.has(method);
