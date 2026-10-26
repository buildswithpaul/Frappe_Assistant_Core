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

// Writes that rebuild a whole document from the payload, so the host reads the current one first.
export const DOC_REPLACING_WRITES = new Set(["frappe.client.save", "frappe.client.submit"]);

// Bidirectional overrides, zero-width and other invisible characters, which can make a prompt
// read differently from what is sent.
const HIDDEN_CHARS = /[­؜᠎​-‏‪-‮⁠-⁤⁦-⁩﻿]/g;

// Keys the server assigns, which a payload cannot change: never shown. Everything else is shown.
const SERVER_KEYS = new Set(["creation", "modified", "modified_by", "__islocal", "__unsaved"]);
const isServerKey = (key) => SERVER_KEYS.has(key) || key.startsWith("_");
// A document's own doctype and name are in the prompt's sentence, not its field list.
const isNamingKey = (key) => key === "doctype" || key === "name";
// A child row's position, which the server renumbers.
const isRowKey = (key) => isServerKey(key) || key === "idx";
// Keys a page may not set on a record it inserts or saves: whose it is and where it hangs.
const FORBIDDEN_TOP_KEYS = ["owner", "parent", "parenttype", "parentfield"];
// Kept when a save leaves them out, so not listed as blanked.
const KEPT_ON_SAVE = new Set(["doctype", "name", "docstatus", "idx", "owner", "parent", "parenttype", "parentfield"]);

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

const isEmpty = (value) =>
	value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0);

/**
 * The payload as Frappe will read it, so what is described is what runs. set_value's fieldname
 * becomes the object Frappe would build (frappe/client.py: a falsy value makes a string fieldname
 * JSON, or a field set to ""); a doc given as a JSON string becomes an object. Returns null for a
 * payload Frappe could not read as described.
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
		return { ...rest, fieldname: values };
	}
	if (["frappe.client.insert", "frappe.client.save", "frappe.client.submit"].includes(method)) {
		const doc = parseDoc(payload.doc);
		// The record is the one in doc; a top-level doctype or name that says otherwise is refused.
		if (!doc || typeof doc.doctype !== "string" || !doc.doctype) return null;
		if (payload.doctype !== undefined && payload.doctype !== doc.doctype) return null;
		if (payload.name !== undefined && payload.name !== doc.name) return null;
		if (DOC_REPLACING_WRITES.has(method) && (typeof doc.name !== "string" || !doc.name)) return null;
		if (method !== "frappe.client.submit") {
			// Insert and save only make drafts; submitting and cancelling are their own calls.
			if (doc.docstatus !== undefined && doc.docstatus !== 0) return null;
			if (FORBIDDEN_TOP_KEYS.some((key) => key in doc)) return null;
		}
		return { ...payload, doc };
	}
	return payload;
}

/**
 * Whether a save or submit fits the document as it is now: a save must not change its docstatus.
 *
 * @param {object} current the document read just before asking
 */
export function fitsCurrentDoc(method, payload, current) {
	if (method !== "frappe.client.save") return true;
	return (payload.doc.docstatus ?? 0) === (current.docstatus ?? 0);
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

// A child table's rows, each as its fields.
const rowsOf = (value, text) =>
	value.map((row) =>
		isPlainObject(row)
			? Object.entries(row)
					.filter(([key]) => !isRowKey(key))
					.map(([name, cell]) => ({ name: text(name), value: text(cell) }))
			: [{ name: "", value: text(row) }],
	);

function field(name, value, text, extra = {}) {
	if (Array.isArray(value)) return { name: text(name), value: "", rows: rowsOf(value, text), ...extra };
	return { name: text(name), value: text(value), ...extra };
}

// Every field a document payload sets; with the current document, how each changes and what a
// replacing write would blank or empty.
function docFields(doc, text, current) {
	const fields = Object.entries(doc)
		.filter(([key]) => !isServerKey(key) && !isNamingKey(key))
		.map(([key, value]) => {
			if (!current) return field(key, value, text);
			const before = current[key];
			const same = JSON.stringify(before ?? null) === JSON.stringify(value ?? null);
			const extra = { status: same ? "same" : "changed" };
			if (!Array.isArray(value)) extra.before = text(before ?? "");
			else extra.beforeRows = Array.isArray(before) ? before.length : 0;
			return field(key, value, text, extra);
		});
	if (current) {
		for (const [key, before] of Object.entries(current)) {
			if (isServerKey(key) || KEPT_ON_SAVE.has(key) || key in doc || isEmpty(before)) continue;
			const table = Array.isArray(before);
			fields.push({
				name: text(key),
				value: "",
				before: table ? "" : text(before),
				beforeRows: table ? before.length : undefined,
				status: table ? "emptied" : "blanked",
			});
		}
	}
	return fields;
}

/**
 * The prompt for a call: {message, note, fields, trustable, hiddenChars}.
 *
 * @param {string} method
 * @param {object} payload the normalised payload, exactly as it will be sent
 * @param {object} [current] the document as it is now, for save and submit
 */
export function describePageRequest(method, payload = {}, current = null) {
	const { text, state } = textMaker();
	let request;
	if (method === "frappe.client.set_value") {
		request = {
			message: __("This page wants to change these fields on {0} {1}.", [text(payload.doctype), text(payload.name)]),
			fields: Object.entries(payload.fieldname || {}).map(([key, value]) => field(key, value, text)),
		};
	} else if (method === "frappe.client.insert") {
		request = {
			message: __("This page wants to create a new {0} with these fields.", [text(payload.doc.doctype)]),
			fields: docFields(payload.doc, text),
		};
	} else if (method === "frappe.client.save") {
		request = {
			message: __("This page wants to save {0} {1}. The record will hold exactly these fields.", [
				text(payload.doc.doctype),
				text(payload.doc.name),
			]),
			fields: docFields(payload.doc, text, current),
		};
	} else if (method === "frappe.client.submit") {
		request = {
			message: __("This page wants to submit {0} {1} with these fields. Submitting can't be undone.", [
				text(payload.doc.doctype),
				text(payload.doc.name),
			]),
			fields: docFields(payload.doc, text, current),
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
	const trustable = mayTrustForPage(method);
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
 * Whether "Allow for this page" is offered: only for a method with no dot in its name that is not
 * one of Frappe's own handler commands, which is a Server Script API method, the kind FACO writes.
 * Any dotted method (frappe.*, erpnext.*, any app's module, savedocs, insert_many, bulk_update,
 * rename_doc, delete_items, apply_workflow), run_doc_method and every record write is allowed one
 * call at a time, described in full.
 */
export const mayTrustForPage = (method) =>
	!method.includes(".") && !FRAPPE_HANDLER_COMMANDS.has(method) && !RECORD_WRITES.has(method);
