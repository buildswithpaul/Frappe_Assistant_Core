/**
 * What an open page has shown that FAC's read tools hide from FACO, so FACO's screenshot can look
 * without asking when the answer is nothing.
 *
 * A page's script reads in the user's own session, outside the masking FAC's tools apply
 * (core/security_config.py SENSITIVE_FIELDS). Every call the page makes passes through `watch`,
 * which checks the fields it asks for and the field names in its answer against get_page's
 * `withheld`. Only a personal page's frame sends every call through here: a shared page runs in
 * the chat's own document, where its script could fetch past the watch.
 */
import { PAGE_API_CHECK, PAGE_READ_METHODS } from "./pageFrameHost";
import { RECORD_WRITES } from "./pageRequestPrompt";

// Frappe's own reads and writes answer with records, whose field names say what they hold.
const CHECKABLE_METHODS = new Set([...PAGE_READ_METHODS, ...RECORD_WRITES, PAGE_API_CHECK]);
// How far into an answer, and how many values, are searched for field names.
const MAX_DEPTH = 6;
const MAX_NODES = 50000;

const isBlank = (value) => value === null || value === undefined || value === "";

// The field names a call asks for: Frappe's `fields`, `fieldname` and `field` args, as a list, a
// JSON string or, for a child table in Frappe v16, an object.
function requestedFields(args) {
	const names = [];
	const collect = (value) => {
		if (typeof value === "string") names.push(value);
		else if (Array.isArray(value)) value.forEach(collect);
		else if (value && typeof value === "object") {
			for (const [key, item] of Object.entries(value)) {
				collect(key);
				collect(item);
			}
		}
	};
	for (const key of ["fields", "fieldname", "field"]) {
		let value = args?.[key];
		if (typeof value === "string" && /^\s*[[{"]/.test(value)) {
			try {
				value = JSON.parse(value);
			} catch {
				// Not JSON: a single field name.
			}
		}
		collect(value);
	}
	return names;
}

// A field name, bare or through its table (`tabBank Account`.iban, items.item_code), or null for an
// expression: an alias, with or without AS, or a function renames the field in the answer.
function plainField(reference) {
	if (!/^[A-Za-z0-9_.*]*$/.test(reference.replace(/`[^`]*`/g, ""))) return null;
	return reference.split(".").pop().replace(/`/g, "").trim();
}

// A Query Report's column may be "Label:Type/Options:Width", whose field is the label scrubbed.
const columnField = (column) => column.split(":")[0].trim().toLowerCase().replace(/[\s-]+/g, "_");

/**
 * @param {{fields: string[], doctypes: Object<string, string[]>, hidden_doctypes: string[]}|undefined} withheld
 *   get_page's `withheld`; without it nothing can be told, as from an older server.
 */
export function createPageReach(withheld) {
	const known = withheld && Array.isArray(withheld.fields);
	const everywhere = new Set(known ? withheld.fields : []);
	const hiddenDoctypes = new Set(known ? withheld.hidden_doctypes || [] : []);
	const hidesAnything =
		everywhere.size > 0 || hiddenDoctypes.size > 0 || Object.keys(known ? withheld.doctypes || {} : {}).length > 0;
	const fields = new Set();
	const methods = new Set();
	// Field names are lower case; MariaDB reads IBAN as the iban column, so names compare lowered.
	const lower = (name) => String(name).toLowerCase();
	const hiddenFor = (doctype) => new Set([...everywhere, ...(withheld?.doctypes?.[doctype] || [])]);
	// A field read through a link (allocated_to.last_login) is of a doctype only the server knows.
	const hiddenAnywhere = new Set([...everywhere, ...Object.values(known ? withheld.doctypes || {} : {}).flat()]);
	const noteField = (hidden, name) => hidden.has(lower(name)) && fields.add(lower(name));

	// False when the answer was too big or too deep to search to the end. Each record in it is
	// checked against its own doctype's hidden fields, falling back to those of the call's doctype.
	function findFields(answer, callHidden) {
		let nodes = 0;
		let complete = true;
		const visit = (value, depth, hidden) => {
			if (value === null || typeof value !== "object") return;
			if (depth > MAX_DEPTH || ++nodes > MAX_NODES) {
				complete = false;
				return;
			}
			if (Array.isArray(value)) {
				value.forEach((item) => visit(item, depth + 1, hidden));
				return;
			}
			if (typeof value.doctype === "string") {
				if (hiddenDoctypes.has(value.doctype)) fields.add(value.doctype);
				hidden = hiddenFor(value.doctype);
			}
			// A report's column, and a list view's keys, name a field without holding its value.
			if (typeof value.fieldname === "string") noteField(hidden, value.fieldname);
			if (Array.isArray(value.keys)) value.keys.forEach((key) => typeof key === "string" && noteField(hidden, key));
			if (Array.isArray(value.columns)) {
				for (const column of value.columns) if (typeof column === "string") noteField(hidden, columnField(column));
			}
			for (const [key, item] of Object.entries(value)) {
				if (!isBlank(item)) noteField(hidden, key);
				visit(item, depth + 1, hidden);
			}
		};
		visit(answer, 0, callHidden);
		return complete;
	}

	function note(method, args, answer) {
		if (!hidesAnything) return;
		if (!CHECKABLE_METHODS.has(method)) {
			methods.add(method);
			return;
		}
		// A write's answer is the document, which names its own doctype for findFields.
		const doctype = typeof args?.doctype === "string" ? args.doctype : "";
		if (hiddenDoctypes.has(doctype)) fields.add(doctype);
		const hidden = hiddenFor(doctype);
		// A field asked for counts whatever the answer's shape: as_dict=0 answers with bare values.
		for (const reference of requestedFields(args)) {
			const field = plainField(reference);
			if (field === null) methods.add(method);
			else noteField(reference.includes(".") ? hiddenAnywhere : hidden, field);
		}
		if (!findFields(answer, hidden)) methods.add(method);
	}

	return {
		/** Hands back `request` unchanged, noting what its answer shows. */
		watch(method, args, request) {
			return request.then((answer) => {
				note(method, args, answer);
				return answer;
			});
		},
		/** What the page has shown that FACO's tools hide, or null when that can't be told. */
		shown: () => (known ? { fields: [...fields].sort(), methods: [...methods].sort() } : null),
	};
}
