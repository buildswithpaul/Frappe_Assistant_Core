/**
 * The words an approval card leads with: what FACO wants to do, in the user's terms, from the
 * tool's own arguments ("Create Customer “MIGTEST Trader 01”", "Publish the work-planner page").
 */

import { __ } from "@/utils/i18n";
import { baseToolName } from "@/utils/toolNames";
import { goesLiveFields, isValidateOnly } from "./customisation";
import { flattenInput, formatToolName } from "./helpers";

// Fields that name a new record, in the order a person would recognise it by.
const LABEL_KEYS = [
	"title",
	"subject",
	"full_name",
	"customer_name",
	"supplier_name",
	"item_name",
	"employee_name",
	"lead_name",
	"first_name",
	"label",
	"description",
	"name",
];
const MAX_LABEL = 48;

// Each action is a whole sentence for translators: word order differs between languages.
const ACTIONS = {
	submit: (doctype, name) => (name ? __("Submit {0} {1}", [doctype, name]) : __("Submit {0}", [doctype])),
	cancel: (doctype, name) => (name ? __("Cancel {0} {1}", [doctype, name]) : __("Cancel {0}", [doctype])),
	amend: (doctype, name) => (name ? __("Amend {0} {1}", [doctype, name]) : __("Amend {0}", [doctype])),
};

function shorten(text) {
	const plain = String(text)
		.replace(/<[^>]*>/g, " ")
		.replace(/\s+/g, " ")
		.trim();
	return plain.length > MAX_LABEL ? `${plain.slice(0, MAX_LABEL - 1)}…` : plain;
}

function labelKey(fields) {
	return LABEL_KEYS.find((k) => typeof fields[k] === "string" && fields[k].trim());
}

function newRecordLabel(fields) {
	const key = labelKey(fields);
	return key ? shorten(fields[key]) : "";
}

// What switching a code record on is called, per doctype that has a switch.
function goLiveHeadline(doctype, name) {
	if (doctype === "FAC Page") return __("Publish the {0} page", [name]);
	if (doctype === "Notification") return __("Switch on the {0} notification", [name]);
	if (doctype === "Client Script") return __("Switch on the {0} form script", [name]);
	return __("Switch on the {0} script", [name]);
}

/** The card title for an approval block. */
export function approvalHeadline(block) {
	const tool = baseToolName(block?.tool_name);
	const input = block?.input && typeof block.input === "object" ? block.input : null;
	if (!input) return formatToolName(tool);
	const fields = flattenInput(input);
	const doctype = fields.doctype;
	const name = fields.name ?? fields.docname;
	if (!doctype) return formatToolName(tool);

	if (tool === "create_document") {
		const label = newRecordLabel(fields);
		if (isValidateOnly(tool, input)) {
			return label ? __("Check {0} “{1}”", [doctype, label]) : __("Check {0}", [doctype]);
		}
		return label ? __("Create {0} “{1}”", [doctype, label]) : __("Create {0}", [doctype]);
	}
	if (tool === "update_document") {
		if (isValidateOnly(tool, input)) {
			return name ? __("Check changes to {0} {1}", [doctype, name]) : __("Check changes to {0}", [doctype]);
		}
		if (goesLiveFields(tool, input).length) return goLiveHeadline(doctype, name);
		return name ? __("Update {0} {1}", [doctype, name]) : __("Update {0}", [doctype]);
	}
	if (tool === "delete_document") return name ? __("Delete {0} {1}", [doctype, name]) : __("Delete {0}", [doctype]);
	if (tool === "document_action") {
		const sentence = ACTIONS[String(fields.action || "").toLowerCase()];
		if (sentence) return sentence(doctype, name);
		return name ? `${formatToolName(fields.action || tool)} ${doctype} ${name}` : `${formatToolName(fields.action || tool)} ${doctype}`;
	}
	return formatToolName(tool);
}

// What "don't ask again" covers: AR remembers it per tool, for every doctype.
const TRUST_SCOPES = {
	create_document: () => __("Don't ask again when FACO creates records"),
	update_document: () => __("Don't ask again when FACO updates records"),
	delete_document: () => __("Don't ask again when FACO deletes records"),
	document_action: () => __("Don't ask again when FACO submits, cancels or amends records"),
};

/** The "don't ask again" label, naming what the trust actually covers. */
export function trustLabel(toolName) {
	const scope = TRUST_SCOPES[baseToolName(toolName)];
	return scope ? scope() : __("Don't ask again for {0}", [formatToolName(baseToolName(toolName))]);
}

/** The identity keys a headline already names, so the field list need not repeat them. */
export function headlineKeys(block) {
	const tool = baseToolName(block?.tool_name);
	if (!block?.input || typeof block.input !== "object" || !flattenInput(block.input).doctype) return [];
	if (tool === "create_document") {
		// A label long enough to be shortened in the title still shows whole in the fields.
		const fields = flattenInput(block.input);
		const key = labelKey(fields);
		return key && shorten(fields[key]) === fields[key].trim() ? ["doctype", key] : ["doctype"];
	}
	if (tool === "document_action") return ["doctype", "name", "docname", "action"];
	if (tool === "update_document" || tool === "delete_document") return ["doctype", "name", "docname"];
	return [];
}
