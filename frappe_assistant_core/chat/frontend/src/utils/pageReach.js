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

// An arg as Frappe reads it: a JSON string is parsed back, anything else is kept as it is.
function parsedArg(value) {
	if (typeof value !== "string" || !/^\s*[[{"]/.test(value)) return value;
	try {
		return JSON.parse(value);
	} catch {
		return value;
	}
}

/**
 * Every field a call names, as {reference, anywhere}: those it asks for (`fields`, `fieldname`,
 * `field`), filters on (`filters`, `or_filters`) or sorts and groups by (`order_by`, `group_by`).
 * A filter or a sort narrows which records show, so it gives a field away one query at a time.
 * `anywhere` marks a field of a doctype only the server knows (a child table's, or a filter's
 * named doctype), to check against every doctype's hidden fields.
 */
function referencedFields(args) {
	const found = [];
	const collect = (value, anywhere) => {
		if (typeof value === "string") found.push({ reference: value, anywhere });
		else if (Array.isArray(value)) value.forEach((item) => collect(item, anywhere));
		else if (value && typeof value === "object") {
			// Frappe v16 names a child table's fields as {table_field: [fields]}.
			for (const [key, item] of Object.entries(value)) {
				collect(key, anywhere);
				collect(item, true);
			}
		}
	};
	for (const key of ["fields", "fieldname", "field"]) collect(parsedArg(args?.[key]), false);
	for (const key of ["filters", "or_filters"]) {
		const filters = parsedArg(args?.[key]);
		if (typeof filters === "string") found.push({ reference: filters, anywhere: true });
		else if (Array.isArray(filters)) {
			// [field, operator, value], or [doctype, field, operator, value].
			for (const filter of filters) {
				if (typeof filter === "string") found.push({ reference: filter, anywhere: true });
				else if (filter && typeof filter === "object" && !Array.isArray(filter)) {
					Object.keys(filter).forEach((field) => found.push({ reference: field, anywhere: true }));
				}
				else if (filter.length >= 4) found.push({ reference: String(filter[1]), anywhere: true });
				else found.push({ reference: String(filter[0]), anywhere: false });
			}
		} else if (filters && typeof filters === "object") {
			Object.keys(filters).forEach((field) => found.push({ reference: field, anywhere: false }));
		}
	}
	for (const key of ["order_by", "group_by"]) {
		if (typeof args?.[key] !== "string") continue;
		for (const part of args[key].split(",")) {
			const reference = part.trim().replace(/\s+(asc|desc)$/i, "");
			if (reference) found.push({ reference, anywhere: false });
		}
	}
	return found;
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
		// A field named counts whatever the answer's shape: as_dict=0 answers with bare values, so
		// every field asked for that way can't be checked by its key.
		const asList = [0, false, "0", "false"].includes(args?.as_dict);
		for (const { reference, anywhere } of referencedFields(args)) {
			const field = plainField(reference);
			if (field === null || (field === "*" && asList)) methods.add(method);
			else noteField(anywhere || reference.includes(".") ? hiddenAnywhere : hidden, field);
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
