/**
 * Helpers for interaction cards.
 *
 * Lives next to the interaction sub-components rather than in /utils because
 * the formatting choices here are specific to how an MCP tool's `input` dict
 * surfaces to the user during approval — not general-purpose formatters.
 */

const MAX_VALUE_LEN = 120;

// Field-name patterns that mark a value as money or a date for display.
// Used by the approval table to render figures in tabular mono so values
// align on the decimal, and to flag money for the gold accent (spec §2.1:
// gold is used on money only). Matching is on the *flattened* key name.
const MONEY_KEY_RE =
	/(amount|total|rate|price|cost|tax|discount|balance|paid|outstanding|grand_total|net_total|conversion_rate|qty|quantity)/i;
const DATE_KEY_RE = /(date|_at|posting|due|delivery|transaction|valid_from|valid_till)/i;
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?/;

function isPlainObject(v) {
	return v && typeof v === "object" && !Array.isArray(v);
}

/**
 * Flatten a tool input dict for human display.
 *
 * MCP tools commonly nest the actual fields one level deep under a key like
 * `data`, `fields`, `values`, or `updates`. To the user, those nested fields
 * ARE the meaningful detail — flatten them onto the top level so each field
 * gets its own row. Boilerplate keys (`validate_only`, `ignore_permissions`,
 * `ignore_mandatory`) are dropped so the approval card stays focused on the
 * actual changes the user is being asked to authorize.
 */
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
			}
		}
	}

	const skipKeys = new Set(["validate_only", "ignore_permissions", "ignore_mandatory"]);
	for (const [key, value] of Object.entries(input)) {
		if (key in result || nestedKeys.includes(key) || skipKeys.has(key)) continue;
		if (!isPlainObject(value)) result[key] = value;
	}

	return result;
}

export function formatToolName(name) {
	if (!name) return "Action";
	return name
		.replace(/_/g, " ")
		.split(" ")
		.map((w) => w.charAt(0).toUpperCase() + w.slice(1))
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
	const s = String(value);
	if (s.length > MAX_VALUE_LEN) return s.slice(0, MAX_VALUE_LEN) + "…";
	return s;
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
	const priorityOrder = ["doctype", "name", "docname", "title", "customer", "status"];
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
