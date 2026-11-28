/**
 * What a tool call's drawer shows, worked out from the block alone: the request as plain-language
 * pills, the result as a table, a record or text, and the request and response for Raw.
 * Pure, so each rule is unit tested without mounting a component.
 *
 * Results come from the user's site and from other MCP servers, in whatever shape each tool
 * chose, so every rule here either recognises a shape or leaves the value to Raw.
 */

import { __ } from "@/utils/i18n";
import { baseToolName } from "@/utils/toolNames";
import { failureReason, toolFailed, toolResult, unfenced } from "@/utils/toolResult";
import { formatJson } from "./formatJson";
import { pythonValues } from "./pythonData";

export const SCRIPT_TOOL = "run_script";

const MAX_COLUMNS = 6;
const MAX_FIELDS = 12;
const MAX_PILL_CHARS = 80;
const MAX_VALUE_CHARS = 200;
const MAX_TEXT_CHARS = 2000;
const MAX_NAMED_FIELDS = 4;
const MAX_ERROR_CHARS = 400;
// A script may print megabytes; reading that as data would freeze the tab.
const MAX_PRINTED_CHARS = 200000;
const MAX_HIGHLIGHT_CHARS = 100000;
// block_builder.truncate_result_for_emit: what a large result looks like until the page is reloaded.
const TRUNCATION_NOTE = "…[truncated — full result available on reload]";
// The keys a tool puts its list of records under. Only these: any other list (a write's
// `warnings`) is detail, and reading it as the result would hide the record it came with.
const LIST_KEYS = ["data", "results", "rows", "documents", "items", "reports", "fields", "doctypes"];
const WRITE_TOOLS = new Set(["create_document", "update_document", "delete_document", "document_action"]);
const YES_NO_FIELD = /^(is_|has_|allow_|enable_|disable_)|^(enabled|disabled)$/;
const OPERATORS = new Map([
	["=", () => __("is")],
	["!=", () => __("is not")],
	[">", () => __("is more than")],
	["<", () => __("is less than")],
	[">=", () => __("is at least")],
	["<=", () => __("is at most")],
	["like", () => __("contains")],
	["not like", () => __("does not contain")],
	["in", () => __("is one of")],
	["not in", () => __("is none of")],
	["between", () => __("is between")],
	["is", () => __("is")],
]);

const isObject = (value) => Boolean(value) && typeof value === "object" && !Array.isArray(value);
const isScalar = (value) => ["string", "number", "boolean"].includes(typeof value);
const clip = (text, max) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

export function isScript(block) {
	return block?.tool_name === SCRIPT_TOOL;
}

/** A fieldname as a form would label it: "default_currency" → "Default currency". */
export function fieldLabel(name) {
	const words = String(name ?? "")
		.replace(/([a-z0-9])([A-Z])/g, "$1 $2")
		.replace(/[_\s]+/g, " ")
		.trim()
		.toLowerCase();
	return words.charAt(0).toUpperCase() + words.slice(1);
}

function yesNo(field, value) {
	if (value === true || (value === 1 && YES_NO_FIELD.test(field))) return __("Yes");
	if (value === false || (value === 0 && YES_NO_FIELD.test(field))) return __("No");
	return null;
}

// "%abc%" contains, "abc%" starts with, "%abc" ends with: the wildcards decide the sentence.
function likePill(label, pattern, negated) {
	const text = String(pattern);
	const core = text.replace(/^%+|%+$/g, "");
	const starts = text.startsWith("%");
	const ends = text.endsWith("%");
	if (negated) return { label: `${label} ${__("does not contain")}`, value: core };
	if (starts && !ends) return { label: `${label} ${__("ends with")}`, value: core };
	if (ends && !starts) return { label: `${label} ${__("starts with")}`, value: core };
	return { label: `${label} ${__("contains")}`, value: core };
}

function filterPill(field, operator, value) {
	const label = fieldLabel(field);
	const op = String(operator).toLowerCase();
	if (value === null || value === undefined) return { label, value: op === "!=" ? __("is set") : __("is not set") };
	if (op.endsWith("like")) return likePill(label, value, op.startsWith("not"));
	const phrase = OPERATORS.has(op) ? OPERATORS.get(op)() : op;
	const shown =
		op === "between" && Array.isArray(value)
			? value.join(` ${__("and")} `)
			: Array.isArray(value)
			? value.join(", ")
			: yesNo(field, value) ?? String(value);
	return { label: `${label} ${phrase}`, value: shown };
}

// Frappe takes {field: value}, {field: [operator, value]}, and rows of [field, value],
// [field, operator, value] or [doctype, field, operator, value]. A report's filters are plain
// {field: value}, where a two-item list is two values, so the first item must be an operator.
function filterRows(filters) {
	if (isObject(filters)) {
		return Object.entries(filters).map(([field, value]) =>
			Array.isArray(value) && value.length === 2 && OPERATORS.has(String(value[0]).toLowerCase())
				? [field, value[0], value[1]]
				: [field, Array.isArray(value) ? "in" : "=", value],
		);
	}
	if (!Array.isArray(filters)) return [];
	return filters
		.filter(Array.isArray)
		.map((row) => (row.length === 2 ? [row[0], "=", row[1]] : row.length === 4 ? row.slice(1) : row))
		.filter((row) => row.length === 3);
}

function filterPills(filters) {
	let parsed = filters;
	if (typeof filters === "string") {
		try {
			parsed = JSON.parse(filters);
		} catch {
			return [];
		}
	}
	return filterRows(parsed)
		.filter(([field]) => typeof field === "string")
		.map(([field, operator, value]) => filterPill(field, operator, value));
}

// "field", "field desc" or "`tabDoctype`.`field` desc". The first field decides the sentence; a
// second one is rare and is in Raw, and an expression is left to Raw altogether.
const ORDER_BY = /^(?:`[^`]+`\.|\w+\.)?`?(\w+)`?(?:\s+(asc|desc))?$/i;

function orderPills(orderBy) {
	const match = typeof orderBy === "string" && ORDER_BY.exec(orderBy.split(",")[0].trim());
	if (!match) return [];
	const descending = (match[2] || "").toLowerCase() === "desc";
	return [{ label: __("Sorted by"), value: `${fieldLabel(match[1])}, ${descending ? __("descending") : __("ascending")}` }];
}

function fieldsPills(fields) {
	if (!Array.isArray(fields) || !fields.length) return [];
	const named = fields.length <= MAX_NAMED_FIELDS && fields.every((field) => typeof field === "string");
	return [{ label: __("Fields"), value: named ? fields.map(fieldLabel).join(", ") : String(fields.length) }];
}

function scalarPills(values) {
	return Object.entries(values)
		.filter(([, value]) => isScalar(value) && String(value) !== "")
		.map(([key, value]) => ({ label: fieldLabel(key), value: yesNo(key, value) ?? String(value) }));
}

const PILL_FOR = new Map([
	// The row above the drawer already names the doctype.
	["doctype", () => []],
	["filters", filterPills],
	["fields", fieldsPills],
	["order_by", orderPills],
	["limit", (limit) => (limit ? [{ label: __("Up to"), value: String(limit) }] : [])],
	["txt", (text) => (text ? [{ label: __("Search for"), value: String(text) }] : [])],
	["data", (data) => (isObject(data) ? scalarPills(data) : [])],
]);
PILL_FOR.set("page_length", PILL_FOR.get("limit"));
PILL_FOR.set("search_term", PILL_FOR.get("txt"));

/** The request in plain words, one `{label, value}` per thing asked for. Anything long or nested is left to Raw. */
export function requestPills(input) {
	if (!isObject(input)) return [];
	return Object.entries(input)
		.flatMap(([key, value]) => (PILL_FOR.has(key) ? PILL_FOR.get(key)(value) : scalarPills({ [key]: value })))
		.filter((pill) => pill.value.length <= MAX_PILL_CHARS);
}

function clean(value) {
	return typeof value === "string" ? unfenced(value) : value;
}

// A report column is {label, fieldname} or the legacy "Label:Type/Options:Width".
function reportColumn(column, index) {
	const label = isObject(column) ? column.label || fieldLabel(column.fieldname) : String(column).split(":")[0];
	const fieldname = isObject(column) ? column.fieldname : label.toLowerCase().replace(/\s+/g, "_");
	return { key: `c${index}`, label, fieldname };
}

// A report's rows are dicts keyed by fieldname or lists in column order, and a totals row is a
// list even when the rest are dicts (frappe.desk.query_report.add_total_row).
function reportTable(rows, columns) {
	if (!rows.every((row) => Array.isArray(row) || isObject(row))) return null;
	const all = columns.map(reportColumn);
	return {
		columns: all.map(({ key, label }) => ({ key, label })),
		rows: rows.map((row) =>
			Object.fromEntries(all.map(({ key, fieldname }, i) => [key, clean(Array.isArray(row) ? row[i] : row[fieldname])])),
		),
	};
}

function recordTable(rows) {
	if (!rows.every(isObject)) return null;
	const keys = [...new Set(rows.slice(0, 20).flatMap(Object.keys))];
	return {
		columns: keys.map((key) => ({ key, label: fieldLabel(key) })),
		rows: rows.map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) => [key, clean(value)]))),
	};
}

function tableFrom(rows, reportColumns, total) {
	const table = Array.isArray(reportColumns) && reportColumns.length ? reportTable(rows, reportColumns) : recordTable(rows);
	if (!table) return null;
	return {
		kind: "table",
		columns: table.columns.slice(0, MAX_COLUMNS),
		hiddenColumns: Math.max(0, table.columns.length - MAX_COLUMNS),
		rows: table.rows,
		total: Number.isInteger(total) && total >= table.rows.length ? total : table.rows.length,
	};
}

function recordView(values) {
	const fields = Object.entries(values)
		.map(([key, value]) => {
			if (Array.isArray(value)) {
				return value.length ? { label: fieldLabel(key), value: value.length === 1 ? __("1 row") : __("{0} rows", [value.length]) } : null;
			}
			if (!isScalar(value) || String(value) === "") return null;
			return { label: fieldLabel(key), value: clip(yesNo(key, value) ?? String(clean(value)), MAX_VALUE_CHARS) };
		})
		.filter(Boolean);
	return { kind: "record", fields: fields.slice(0, MAX_FIELDS), more: Math.max(0, fields.length - MAX_FIELDS) };
}

function textParts(result) {
	const parts = Array.isArray(result) ? result : Array.isArray(result?.content) ? result.content : [];
	return parts.map((part) => (typeof part?.text === "string" ? part.text : "")).filter(Boolean);
}

function contentText(result) {
	return typeof result === "string" ? result : textParts(result).join("\n");
}

/** A large result is cut short on the live socket; the stored copy, read on reload, is whole. */
export function isTruncated(block) {
	const result = block?.result;
	if (result?._truncated === true) return true;
	return contentText(result).trimEnd().endsWith(TRUNCATION_NOTE);
}

/**
 * How to show a tool's result: `table` (a list of records), `empty` (a list with nothing in it),
 * `record` (one record, or a flat answer), `text`, `error`, `truncated` (too large to show until
 * the page is reloaded), or `none` when there is nothing yet.
 */
export function resultView(block) {
	if (toolFailed(block)) return { kind: "error", text: failureReason(block, MAX_ERROR_CHARS) };
	if (isTruncated(block)) return { kind: "truncated" };
	const result = toolResult(block);
	if (!Object.keys(result).length) {
		const text = contentText(block?.result);
		return text ? { kind: "text", text: clip(text, MAX_TEXT_CHARS) } : { kind: "none" };
	}
	const list = result[LIST_KEYS.find((name) => Array.isArray(result[name]))];
	if (list) {
		if (!list.length) return { kind: "empty" };
		const table = tableFrom(list, result.columns, result.total_count ?? result.count);
		if (table) return table;
	}
	const { success: _success, ...rest } = isObject(result.data) ? result.data : result;
	const record = recordView(rest);
	return record.fields.length ? record : { kind: "none" };
}

/**
 * How many records a read found, or null when the call is not a list. A script and a write are
 * never counted: whatever list they return, "N found" would misdescribe them.
 */
export function resultCount(block) {
	if (isScript(block) || WRITE_TOOLS.has(baseToolName(block?.tool_name))) return null;
	const view = resultView(block);
	if (view.kind === "table") return view.total;
	return view.kind === "empty" ? 0 : null;
}

/** A row's value as one table cell's text. A row without the column has no value, whatever the column is called. */
export function cellText(row, key) {
	const value = Object.hasOwn(row, key) ? row[key] : undefined;
	if (value === null || value === undefined || value === "") return "—";
	return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export function scriptCode(block) {
	return typeof block?.input?.code === "string" ? block.input.code : "";
}

/** What a script printed, or "" when nothing readable has arrived (still running, or cut short). */
export function scriptOutput(block) {
	return isTruncated(block) ? "" : contentText(block?.result);
}

/** The language to highlight `text` as: none once it is large enough to stall the page. */
export function languageFor(text, language) {
	return text.length > MAX_HIGHLIGHT_CHARS ? "" : language;
}

function stringify(value) {
	const text = JSON.stringify(value);
	return text === undefined ? "" : formatJson(text);
}

export function rawRequest(block) {
	return isObject(block?.input) && Object.keys(block.input).length ? stringify(block.input) : "";
}

/**
 * The response for Raw. A result that is one piece of text is that text, re-indented when it is
 * JSON. Anything more (several parts, an image, a structured copy beside the text) is shown whole,
 * so nothing a tool sent is left out.
 */
export function rawResponse(block) {
	const result = block?.result;
	if (result === null || result === undefined) return "";
	if (typeof result === "string") return formatJson(result);
	if (result._truncated === true) return typeof result.preview === "string" ? result.preview : "";
	const onlyText = Array.isArray(result) && result.length === 1 && Object.keys(result[0] ?? {}).every((key) => key === "text" || key === "type");
	return onlyText && typeof result[0].text === "string" ? formatJson(result[0].text) : stringify(result);
}

// A script that printed json.dumps(...): the whole text as one value, or a value per line.
function jsonValues(text) {
	for (const pieces of [[text], text.split("\n").filter((line) => line.trim())]) {
		try {
			const values = pieces.map((piece) => JSON.parse(piece));
			if (values.every((value) => value !== null && typeof value === "object")) return values;
		} catch {
			// Not JSON read this way; the next reading, or the Python one, may fit.
		}
	}
	return null;
}

/**
 * The values a script printed, when all of it is data: Python lists, dicts and tuples
 * (`print(a, b)` gives two) or a JSON value per line. Null for anything else, a sentence or a
 * `datetime.date(...)` included, so the caller shows the text as it was printed.
 */
export function printedValues(text) {
	if (typeof text !== "string" || !text.trim() || text.length > MAX_PRINTED_CHARS) return null;
	return jsonValues(text) ?? pythonValues(text);
}

function tableOf(value) {
	return Array.isArray(value) && value.length ? tableFrom(value) : null;
}

/**
 * One printed value as the sections to show. A list of records is a table. A dict that holds lists
 * of records is a table for each, titled by its key, with the dict's plain values as fields.
 * Anything else is formatted data.
 */
export function printedSections(value) {
	const whole = tableOf(value);
	if (whole) return [{ table: whole }];
	const tables = isObject(value)
		? Object.entries(value)
				.map(([key, item]) => ({ key, title: fieldLabel(key), table: tableOf(item) }))
				.filter((section) => section.table)
		: [];
	if (!tables.length) return [{ json: stringify(value) }];
	const named = new Set(tables.map((section) => section.key));
	const rest = Object.fromEntries(Object.entries(value).filter(([key]) => !named.has(key)));
	const { fields } = recordView(rest);
	return [...tables.map(({ title, table }) => ({ title, table })), ...(fields.length ? [{ fields }] : [])];
}
