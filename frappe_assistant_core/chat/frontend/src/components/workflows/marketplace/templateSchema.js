import { __ } from "@/utils/i18n";
import { parseJsonMaybe } from "@/utils/json";

const TYPE_ALIASES = { string: "text", data: "text", integer: "int", number: "float", boolean: "check", bool: "check" };
const KNOWN_TYPES = new Set(["link", "email", "int", "float", "check", "select", "text"]);
// Values that must exist on THIS site: a template's sample value is never right.
const NEVER_PREFILL = new Set(["link", "email"]);

const humanize = (key) => String(key).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function toList(value, separator = /[\n,]/) {
	if (Array.isArray(value)) return value.map(String).map((s) => s.trim()).filter(Boolean);
	if (typeof value === "string") return value.split(separator).map((s) => s.trim()).filter(Boolean);
	return [];
}

// The server reads a string `options` one choice per line; a comma is part of a choice.
const toChoices = (value) => toList(value, /\n/);

function normalizeField(key, def, defaults) {
	const raw = def && typeof def === "object" ? def : { description: String(def ?? "") };
	let type = String(raw.type || "").toLowerCase();
	type = TYPE_ALIASES[type] || type;
	if (Array.isArray(raw.enum) && raw.enum.length) type = "select";
	if (!KNOWN_TYPES.has(type)) type = "text";

	let options = null;
	if (type === "select") options = toChoices(raw.options).length ? toChoices(raw.options) : toChoices(raw.enum);
	if (type === "link") {
		options = typeof raw.options === "string" && raw.options.trim() ? raw.options.trim() : null;
		if (!options) type = "text";
	}

	return {
		key,
		label: raw.label || humanize(key),
		description: raw.description || "",
		required: !!raw.required,
		type,
		options,
		default: raw.default ?? defaults?.[key] ?? (type === "check" ? false : ""),
	};
}

export function normalizeVariableSchema(rawSchema, rawDefaults) {
	const schema = parseJsonMaybe(rawSchema, {});
	const defaults = parseJsonMaybe(rawDefaults, {}) || {};
	if (Array.isArray(schema)) {
		return schema
			.filter((d) => (typeof d === "string" && d.trim()) || (d && (d.name || d.key)))
			.map((d) =>
				typeof d === "string"
					? normalizeField(d, { label: d, type: "text" }, defaults)
					: normalizeField(d.name || d.key, d, defaults)
			);
	}
	if (!schema || typeof schema !== "object") return [];
	return Object.entries(schema).map(([key, def]) => normalizeField(key, def, defaults));
}

export function initialValues(fields) {
	const values = {};
	for (const f of fields) {
		if (f.type === "check") values[f.key] = f.default === true || f.default === 1 || f.default === "1";
		else if (NEVER_PREFILL.has(f.type)) values[f.key] = "";
		else values[f.key] = f.default ?? "";
	}
	return values;
}

const isEmpty = (v) => v === null || v === undefined || (typeof v === "string" && !v.trim());
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateVariables(fields, values) {
	const errors = {};
	for (const f of fields) {
		const v = values?.[f.key];
		if (f.type === "check") continue;
		if (isEmpty(v)) {
			if (f.required) errors[f.key] = __("{0} is required", [f.label]);
			continue;
		}
		const s = String(v).trim();
		if (f.type === "email" && !EMAIL.test(s)) errors[f.key] = __("{0} must be an email address", [f.label]);
		if (f.type === "int" && !/^-?\d+$/.test(s)) errors[f.key] = __("{0} must be a whole number", [f.label]);
		if (f.type === "float" && !Number.isFinite(Number(s))) errors[f.key] = __("{0} must be a number", [f.label]);
		if (f.type === "select" && !(f.options || []).includes(s))
			errors[f.key] = __("{0} must be one of the listed options", [f.label]);
	}
	return errors;
}

export function coerceVariables(fields, values) {
	const out = {};
	for (const f of fields) {
		const v = values?.[f.key];
		if (f.type === "check") {
			out[f.key] = !!v;
			continue;
		}
		if (isEmpty(v)) continue;
		const s = String(v).trim();
		if (f.type === "int") out[f.key] = parseInt(s, 10);
		else if (f.type === "float") out[f.key] = Number(s);
		else out[f.key] = s;
	}
	return Object.keys(out).length ? out : null;
}

export function parseRequires(raw) {
	const r = parseJsonMaybe(raw, null);
	if (!r || typeof r !== "object" || Array.isArray(r)) return null;
	return {
		modules: toList(r.modules),
		reports: toList(r.reports),
		tools: toList(r.tools),
		writeTools: toList(r.write_tools),
		minErpnext: r.min_erpnext ? String(r.min_erpnext) : "",
	};
}

export function legacyRequiredTools(template) {
	const raw = template?.required_tools;
	if (Array.isArray(raw)) return raw;
	if (typeof raw !== "string" || !raw.trim()) return [];
	const parsed = parseJsonMaybe(raw.trim(), null);
	return Array.isArray(parsed) ? parsed : toList(raw);
}
