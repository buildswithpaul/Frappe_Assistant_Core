/**
 * Helpers for interaction cards.
 *
 * Lives next to the interaction sub-components rather than in /utils because
 * the formatting choices here are specific to how an MCP tool's `input` dict
 * surfaces to the user during approval — not general-purpose formatters.
 */

import { __ } from "@/utils/i18n";
import { titleWord } from "@/utils/toolLabel";
import { baseToolName } from "@/utils/toolNames";

// A longer value folds to its first PREVIEW_LEN characters, with a control that shows it all.
const PREVIEW_LEN = 120;

// Field-name patterns that mark a value as money or a date for display.
// Used by the approval table to render figures in tabular mono so values
// align on the decimal, and to flag money for the gold accent (spec §2.1:
// gold is used on money only). Matching is on the *flattened* key name.
const MONEY_KEY_RE =
	/(amount|total|rate|price|cost|tax|discount|balance|paid|outstanding|grand_total|net_total|conversion_rate|qty|quantity)/i;
const DATE_KEY_RE = /(date|_at|posting|due|delivery|transaction|valid_from|valid_till)/i;
// Anchored at both ends: a card must never show "a date" for a value that carries more than one.
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?$/;

function isPlainObject(v) {
	return v && typeof v === "object" && !Array.isArray(v);
}

// Fields that hold code or markup. Mirrored in chat/api/current_code.py.
export const CODE_KEYS = [
	"script",
	"condition",
	"query",
	"html",
	"javascript",
	"report_script",
	"css",
	"message",
];

export function isCodeKey(key) {
	return CODE_KEYS.includes(key);
}

// Code keys a single doctype adds, so other doctypes' fields of the same name stay plain.
// The server returns these through GO_LIVE_KEYS in chat/api/current_code.py.
const DOCTYPE_CODE_KEYS = { "FAC Page": ["style"] };

/** True when `key` holds code on a `doctype` record: a CODE_KEYS field or one that doctype adds. */
export function isCodeField(key, doctype) {
	return isCodeKey(key) || Boolean(DOCTYPE_CODE_KEYS[doctype]?.includes(key));
}

const PYTHON_KEYS = new Set(["script", "report_script", "condition"]);

export function codeLanguage(key, doctype) {
	if (key === "script" && doctype === "FAC Page") return "javascript";
	if (key === "style" && doctype === "FAC Page") return "css";
	if (PYTHON_KEYS.has(key)) return "python";
	if (key === "javascript") return "javascript";
	if (key === "query") return "sql";
	if (key === "html" && doctype === "Print Format") return "django";
	return "xml";
}

/** True for a non-empty array of plain objects, i.e. the rows of a child table. */
export function isChildTable(value) {
	return Array.isArray(value) && value.length > 0 && value.every(isPlainObject);
}

/** A list of sentences, such as a migration plan's decisions: shown line by line (#34547). */
export function isTextList(value) {
	return Array.isArray(value) && value.length > 0 && value.every((item) => typeof item === "string");
}

/**
 * What an update does to a child table it is given, when it isn't only the rows it names:
 * update_document clears the table given [], and replaces every row when no row has a `name`
 * (#34540). Null otherwise, and for any other tool.
 */
export function tableReplacement(toolName, value) {
	if (baseToolName(toolName) !== "update_document" || !Array.isArray(value)) return null;
	if (value.length === 0) return __("Removes all its rows");
	if (value.every(isPlainObject) && !value.some((row) => row.name)) {
		return __("Replaces all its rows with {0}", [value.length]);
	}
	return null;
}

/**
 * Flatten a tool input dict for human display.
 *
 * MCP tools commonly nest the actual fields one level deep under a key like
 * `data`, `fields`, `values`, or `updates`. To the user, those nested fields
 * ARE the meaningful detail — flatten them onto the top level so each field
 * gets its own row. Boilerplate keys (`validate_only`, `ignore_permissions`,
 * `ignore_mandatory`) are dropped so the approval card stays focused on the
 * actual changes the user is being asked to authorize. A nested key that collides with a
 * record identity key (`data.name` on an update) is kept as `new_<key>`.
 */
// A value the server fenced as file content (untrusted_output.py), passed back by the model as it
// read it: the card shows the file's text, not the fence's tags and preamble (#34438). A fence is
// just its tags now, the reply saying the preamble once; one with it inside is still read.
const FENCED = /^\s*<import_file_content>\n[^\n]*\n([\s\S]*)\n<\/import_file_content>\s*$/;
const TAGS_ONLY = /^\s*<import_file_content>([\s\S]*)<\/import_file_content>\s*$/;

function unfenced(value) {
	if (Array.isArray(value)) return value.map(unfenced);
	if (typeof value !== "string") return value;
	const match = FENCED.exec(value) || TAGS_ONLY.exec(value);
	return match ? match[1] : value;
}

export function flattenInput(input) {
	const result = {};
	const metaKeys = ["doctype", "name", "docname", "title", "status"];
	const nestedKeys = ["data", "fields", "values", "updates"];

	for (const key of metaKeys) {
		if (input[key] !== undefined && !isPlainObject(input[key])) {
			result[key] = input[key];
		}
	}

	// Merge nested field dicts at top level so each field becomes its own row.
	for (const key of nestedKeys) {
		if (isPlainObject(input[key])) {
			for (const [fk, fv] of Object.entries(input[key])) {
				if (!(fk in result)) result[fk] = fv;
				// A data key that shares a name with the record's identity (a rename) is a change, not a duplicate;
				// compared as trimmed strings so 5 and "5" are the same record, as in update_document.
				else if (metaKeys.includes(fk) && String(result[fk]).trim() !== String(fv).trim() && !isPlainObject(fv)) result[`new_${fk}`] ??= fv;
			}
		}
	}

	// "documents" (several records in one call) is shown record by record, by documentTables.
	const skipKeys = new Set(["validate_only", "ignore_permissions", "ignore_mandatory", "documents"]);
	for (const [key, value] of Object.entries(input)) {
		if (key in result || nestedKeys.includes(key) || skipKeys.has(key)) continue;
		if (!isPlainObject(value)) result[key] = value;
	}

	for (const [key, value] of Object.entries(result)) result[key] = unfenced(value);
	return result;
}

/** How many records a call writes with `documents` (several in one call); 0 without it. */
export function documentCount(input) {
	return input && Array.isArray(input.documents) ? input.documents.length : 0;
}

// Which key names the record, so it can lead its row: the record's own name (an update),
// a prompt name, then a name field (customer_group_name, title, a Market Segment's market_segment).
function nameRank(key, doctype) {
	if (key === "name") return 0;
	if (key === "__newname") return 1;
	if (key === doctype.toLowerCase().replace(/ /g, "_") || /(^title$|_name$)/.test(key)) return 2;
	return 3;
}

/**
 * The records of a call that writes several (`documents`, as create_document and
 * update_document take it), as one table per doctype, in order of first appearance:
 * one column per key any of its records sends, the name first, and one row per record.
 * An update row starts with the record's name. Every key is a column, `_assign` and
 * `__newname` included: the server sets each one on the record, so the card shows each.
 * Returns [] when the input has no such list.
 */
export function documentTables(input) {
	const documents = input && Array.isArray(input.documents) ? input.documents : [];
	const tables = new Map();
	for (const entry of documents) {
		const doc = isPlainObject(entry) ? entry : {};
		const doctype = doc.doctype ? String(doc.doctype) : "Record";
		if (!tables.has(doctype)) tables.set(doctype, { doctype, columns: [], rows: [] });
		const table = tables.get(doctype);
		const named = doc.name != null && doc.name !== "";
		const row = named ? { name: doc.name } : {};
		for (const [key, value] of Object.entries(isPlainObject(doc.data) ? doc.data : {})) {
			// A data name that differs from the record's is a rename, kept as in flattenInput.
			if (key === "name" && named) {
				if (String(value).trim() !== String(doc.name).trim()) row.new_name ??= value;
			} else row[key] = value;
		}
		for (const key of Object.keys(row)) if (!table.columns.includes(key)) table.columns.push(key);
		table.rows.push(row);
	}
	return [...tables.values()].map((table) => ({
		...table,
		columns: table.columns
			.map((key, index) => [key, index])
			.sort((a, b) => nameRank(a[0], table.doctype) - nameRank(b[0], table.doctype) || a[1] - b[1])
			.map(([key]) => key),
	}));
}

/** "Customer Groups" for 2, "Territories", "Addresses", "UOMs"; the doctype itself for 1. */
export function pluralDoctype(doctype, count) {
	if (count === 1) return doctype;
	if (/[^aeiou]y$/i.test(doctype)) return `${doctype.slice(0, -1)}ies`;
	if (/(s|x|z|ch|sh)$/i.test(doctype)) return `${doctype}es`;
	return `${doctype}s`;
}

/** "Create 21: 6 Customer Groups, 3 Territories, 12 UOMs", or "Update 2: 2 Customers". */
export function documentsHeading(toolName, input) {
	const tables = documentTables(input);
	const total = tables.reduce((sum, table) => sum + table.rows.length, 0);
	const counts = tables
		.map((table) => `${table.rows.length} ${pluralDoctype(table.doctype, table.rows.length)}`)
		.join(", ");
	return baseToolName(toolName) === "update_document"
		? __("Update {0}: {1}", [total, counts])
		: __("Create {0}: {1}", [total, counts]);
}

/** A column's heading: the field's words, or the key itself for one that starts with "_". */
export function columnLabel(key) {
	return key.startsWith("_") ? key : formatKey(key);
}

/** A value as text in full, for a record table's cell: nothing is summarised or cut. */
export function cellText(value) {
	if (value == null || value === "") return "—";
	if (typeof value === "boolean") return value ? "Yes" : "No";
	if (Array.isArray(value)) {
		return value.map((v) => (v !== null && typeof v === "object" ? JSON.stringify(v) : String(v))).join(", ");
	}
	if (typeof value === "object") return JSON.stringify(value);
	return String(value);
}

/** True for text too long or with too many lines to show whole in a table cell or field row. */
export function isLongValue(value) {
	return typeof value === "string" && (value.length > PREVIEW_LEN || value.includes("\n"));
}

/** The start of a long value, on one line, for its folded cell. */
export function previewText(value) {
	const line = String(value).replace(/\s+/g, " ").trim();
	return line.length > PREVIEW_LEN ? `${line.slice(0, PREVIEW_LEN)}…` : line;
}

export function formatToolName(name) {
	if (!name) return "Action";
	return name
		.replace(/_/g, " ")
		.split(" ")
		.map(titleWord)
		.join(" ");
}

export function formatKey(key) {
	return key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

export function formatValue(value) {
	if (value == null || value === "") return "—";
	if (Array.isArray(value)) {
		if (value.length === 0) return "—";
		return `${value.length} item${value.length === 1 ? "" : "s"}`;
	}
	if (typeof value === "object") {
		const keys = Object.keys(value);
		return `${keys.length} field${keys.length === 1 ? "" : "s"}`;
	}
	if (typeof value === "boolean") return value ? "Yes" : "No";
	// Never cut: a long value is shown folded by LongValue, which can open it in full.
	return String(value);
}

/**
 * True when a field key looks like a monetary figure. Drives the tabular-mono
 * + gold accent in the approval table. Key-name based (not value parsing) so
 * "0" rates and "1" conversion rates still align in the mono column.
 */
export function isMoneyKey(key) {
	return MONEY_KEY_RE.test(String(key));
}

/** True when the value is an ISO-ish date/datetime string. */
export function isDateValue(value) {
	return typeof value === "string" && ISO_DATE_RE.test(value.trim());
}

/**
 * True when a row's value should render in tabular mono (money keys, date
 * keys, or values that *look* like dates). Used by ApprovalCard to pick the
 * mono class so figures align on the decimal (spec §2.2 numerals).
 */
export function isMonoValue(key, value) {
	if (isMoneyKey(key)) return true;
	if (DATE_KEY_RE.test(String(key))) return true;
	if (isDateValue(value)) return true;
	return false;
}

/**
 * Split a flattened input dict into the rows shown by default and the rows
 * hidden behind "Show all fields ›". Meta/identity keys (doctype, name, …)
 * are ordered first so the user always sees *what record* before the rest.
 * Returns ordered [key, value] pairs (not objects) to keep render order stable.
 */
export function splitDetailFields(flat, primaryCount = 4) {
	const priorityOrder = ["doctype", "name", "new_name", "docname", "title", "customer", "status"];
	const entries = Object.entries(flat || {});
	entries.sort((a, b) => {
		const ai = priorityOrder.indexOf(a[0]);
		const bi = priorityOrder.indexOf(b[0]);
		const av = ai === -1 ? Number.MAX_SAFE_INTEGER : ai;
		const bv = bi === -1 ? Number.MAX_SAFE_INTEGER : bi;
		return av - bv;
	});
	const primary = entries.slice(0, primaryCount);
	const overflow = entries.slice(primaryCount);
	return { primary, overflow, overflowCount: overflow.length };
}

// Check fields arrive as 1/0; a person reads Yes/No. Matched on the field name, since the card
// has no doctype meta to ask.
const CHECK_KEY_RE =
	/^(is_|has_|allow_|enable|disable|published|active|reqd|mandatory|hidden|read_only|bold|in_list_view|in_standard_filter)/i;
const CHECK_VALUES = { 1: true, true: true, 0: false, false: false };
const PLAIN_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?)?$/;

function readableDate(value) {
	const m = PLAIN_DATE_RE.exec(value.trim());
	if (!m) return null;
	const [, y, mo, d, h, mi] = m;
	// Built from the parts so a date never shifts a day across time zones.
	const date = new Date(Number(y), Number(mo) - 1, Number(d), Number(h || 0), Number(mi || 0));
	// A date that rolls over (2026-02-31 → 3 Mar) is not the value FACO sent: show it raw.
	if (date.getFullYear() !== Number(y) || date.getMonth() !== Number(mo) - 1 || date.getDate() !== Number(d)) {
		return null;
	}
	if (Number(h || 0) > 23 || Number(mi || 0) > 59) return null;
	const day = date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
	return h === undefined ? day : `${day}, ${date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
}

/** A field value as the approval table shows it: Yes/No for checks, dates in words, else formatValue. */
export function displayValue(key, value) {
	if (CHECK_KEY_RE.test(String(key)) && String(value) in CHECK_VALUES && typeof value !== "object") {
		return CHECK_VALUES[String(value)] ? __("Yes") : __("No");
	}
	if (typeof value === "string" && isDateValue(value)) return readableDate(value) ?? formatValue(value);
	return formatValue(value);
}
