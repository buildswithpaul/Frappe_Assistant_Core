/**
 * What an approval card says about the write it is asking to make.
 *
 * Only tools we are certain write to the ERP get a line. Read-only and dynamic tools
 * (ask_user, get_skill, run_python_code) may not write, and a false "will write" warning
 * trains users to ignore it on calls that do mutate data.
 */

import { __ } from "@/utils/i18n";
import { flattenInput } from "./helpers";

// The doctypes whose writes change how the site behaves; mirrors the server-side set.
const CUSTOMISATION_DOCTYPES = new Set([
	"Server Script",
	"Client Script",
	"Custom Field",
	"Property Setter",
	"Workflow",
	"Workflow State",
	"Workflow Action Master",
	"Custom DocPerm",
	"DocType",
	"Role",
	"Report",
	"Print Format",
	"Notification",
]);

// A second connection's tools arrive prefixed ("prod_create_document"); the base name decides.
const WRITE_TOOL_NAMES = ["create_document", "update_document", "delete_document", "document_action"];

export function baseToolName(toolName) {
	if (typeof toolName !== "string") return "";
	return WRITE_TOOL_NAMES.find((name) => toolName === name || toolName.endsWith(`_${name}`)) || toolName;
}

// AR flags writes to customisation doctypes on the interrupt reason.
export function isCustomisationRisk(block) {
	return block?.interrupts?.[0]?.reason?.risk === "customisation";
}

const startsWithVowel = (word) => /^[aeiou]/i.test(word);

// One whole sentence per event and article, so each translates as a unit.
const SERVER_SCRIPT_EVENTS = {
	"Before Save": { a: "This code will run every time someone saves a {0}", an: "This code will run every time someone saves an {0}" },
	"After Save": { a: "This code will run every time someone saves a {0}", an: "This code will run every time someone saves an {0}" },
	"Before Submit": { a: "This code will run every time someone submits a {0}", an: "This code will run every time someone submits an {0}" },
	"Before Cancel": { a: "This code will run every time someone cancels a {0}", an: "This code will run every time someone cancels an {0}" },
};
const SERVER_SCRIPT_OTHER_EVENT = {
	a: "This code will run every time someone uses a {0}",
	an: "This code will run every time someone uses an {0}",
};

function serverScriptConsequence(fields) {
	if (fields.script_type === "API") return __("This code will run on the server when called");
	if (fields.script_type === "Scheduler Event") return __("This code will run on a schedule");
	if (!fields.doctype_event || !fields.reference_doctype) return null;
	const sentences = SERVER_SCRIPT_EVENTS[fields.doctype_event] || SERVER_SCRIPT_OTHER_EVENT;
	const doctype = fields.reference_doctype;
	return startsWithVowel(doctype) ? __(sentences.an, [doctype]) : __(sentences.a, [doctype]);
}

function propertySetterConsequence(fields) {
	const doctype = fields.doc_type;
	if (!doctype) return null;
	return startsWithVowel(doctype)
		? __("Changes how an {0} field behaves for everyone", [doctype])
		: __("Changes how a {0} field behaves for everyone", [doctype]);
}

const needs = (field, text) => (fields) => (fields[field] ? __(text, [fields[field]]) : null);
const accessLine = () => __("Changes who can see or do what on this site");

// One line per doctype. A partial update may omit the field that drives the sentence;
// the line is then null and the card falls back to the generic update copy.
const CUSTOMISATION_CONSEQUENCES = {
	"Server Script": serverScriptConsequence,
	"Client Script": needs("dt", "This changes how the {0} form behaves in Desk for everyone"),
	"Custom Field": needs("dt", "Adds a field to every {0}"),
	"Property Setter": propertySetterConsequence,
	Workflow: needs("document_type", "Changes how {0} records are approved for everyone"),
	"Print Format": needs("doc_type", "Changes how {0} prints"),
	Notification: needs("document_type", "Sends messages automatically when {0} records change"),
	Report: needs("ref_doctype", "Adds a report on {0}"),
	Role: accessLine,
	"Custom DocPerm": accessLine,
	DocType: accessLine,
};

/**
 * Plain-language line for a create/update/delete of a customisation record, or null
 * when the write is not one (callers then fall back to the generic write line).
 */
export function customisationConsequence(toolName, input) {
	const tool = baseToolName(toolName);
	if (!["create_document", "update_document", "delete_document"].includes(tool)) return null;
	if (!input || typeof input !== "object") return null;
	const fields = flattenInput(input);
	if (!CUSTOMISATION_DOCTYPES.has(fields.doctype)) return null;
	if (tool === "delete_document") return __("This removes a customisation from your site for everyone");
	return CUSTOMISATION_CONSEQUENCES[fields.doctype]?.(fields) ?? null;
}

// document_action submits, cancels or amends, so its warning follows the requested action.
const DOCUMENT_ACTION_CONSEQUENCES = {
	submit: "This will submit a record — it becomes immutable",
	cancel: "This will cancel a submitted record and reverse its accounting and stock entries",
	amend: "This will create a new draft copy of a cancelled record",
};

const WRITE_CONSEQUENCES = {
	create_document: "This will write a new record to your ERP",
	update_document: "This will modify an existing record in your ERP",
	delete_document: "This will permanently delete a record from your ERP",
};

function documentActionConsequence(input) {
	const action = input && typeof input === "object" ? String(input.action || "submit") : "";
	return (
		DOCUMENT_ACTION_CONSEQUENCES[action.trim().toLowerCase()] ||
		"This will submit, cancel or amend a record in your ERP"
	);
}

export function writeConsequence(toolName, input) {
	const customisation = customisationConsequence(toolName, input);
	if (customisation) return customisation;
	const tool = baseToolName(toolName);
	if (tool === "document_action") return documentActionConsequence(input);
	return WRITE_CONSEQUENCES[tool] || "";
}
