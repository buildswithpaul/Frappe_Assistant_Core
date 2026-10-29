/**
 * Code a write puts live by opening a dormant DocType to other people: the eval: conditions and HTML
 * markup its fields, Custom Fields and Property Setters carry, which ran for nobody while only the
 * system roles could reach it. Server side: chat/api/doctype_code.py.
 */

import { __ } from "@/utils/i18n";
import { baseToolName } from "@/utils/toolNames";
import { codeLanguage, formatKey } from "./helpers";

const isName = (value) => typeof value === "string" && value !== "";

/**
 * What to ask the server about, or null for a write that cannot open a DocType: a DocType update
 * that sets its permissions or makes it a child table ({ target }), or a Custom DocPerm write
 * ({ target } from its parent, or { customDocperm } for an update that leaves the parent out).
 */
export function openingTarget(toolName, input) {
	const tool = baseToolName(toolName);
	const data = input?.data && typeof input.data === "object" ? input.data : {};
	if (input?.doctype === "DocType" && tool === "update_document" && isName(input.name)) {
		return "permissions" in data || "istable" in data ? { target: input.name } : null;
	}
	if (input?.doctype !== "Custom DocPerm" || !["create_document", "update_document"].includes(tool)) return null;
	if (isName(data.parent)) return { target: data.parent };
	return tool === "update_document" && isName(input.name) ? { customDocperm: input.name } : null;
}

/** One code block per entry the server returned, labelled with the record that sets it. */
export function openingCodeBlocks(entries) {
	if (!Array.isArray(entries)) return [];
	return entries.map((entry) => ({
		key: `${entry.source}:${entry.name}:${entry.field}:${entry.key}`,
		label: __("{0} {1}: {2}", [entry.source, entry.field, formatKey(entry.key)]),
		code: String(entry.code ?? ""),
		language: codeLanguage(entry.key, "Custom Field"),
	}));
}
