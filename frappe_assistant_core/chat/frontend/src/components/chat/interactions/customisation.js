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

const SERVER_SCRIPT_EVENT_VERBS = {
	"Before Save": "saves",
	"After Save": "saves",
	"Before Submit": "submits",
	"Before Cancel": "cancels",
};

const article = (word) => (/^[aeiou]/i.test(word) ? "an" : "a");
const withArticle = (word) => `${article(word)} ${word}`;

function serverScriptConsequence(fields) {
	if (fields.script_type === "API") return __("This code will run on the server when called");
	if (fields.script_type === "Scheduler Event") return __("This code will run on a schedule");
	const verb = SERVER_SCRIPT_EVENT_VERBS[fields.doctype_event] || "uses";
	const target = fields.reference_doctype ? withArticle(fields.reference_doctype) : "a record";
	return __("This code will run every time someone {0} {1}", [verb, target]);
}

// One line per doctype, each given the fields of the write; a missing field reads as "record".
const CUSTOMISATION_CONSEQUENCES = {
	"Server Script": serverScriptConsequence,
	"Client Script": (f) => __("This changes how the {0} form behaves in Desk for everyone", [f.dt || "record"]),
	"Custom Field": (f) => __("Adds a field to every {0}", [f.dt || "record"]),
	"Property Setter": (f) =>
		__("Changes how {0} field behaves for everyone", [withArticle(f.doc_type || "record")]),
	Workflow: (f) => __("Changes how {0} records are approved for everyone", [f.document_type || "these"]),
	"Print Format": (f) => __("Changes how {0} prints", [f.doc_type || "a record"]),
	Notification: (f) =>
		__("Sends messages automatically when {0} records change", [f.document_type || "these"]),
	Report: (f) => __("Adds a report on {0}", [f.ref_doctype || "a record"]),
	Role: () => __("Changes who can see or do what on this site"),
	"Custom DocPerm": () => __("Changes who can see or do what on this site"),
	DocType: () => __("Changes who can see or do what on this site"),
};

/**
 * Plain-language line for a create/update/delete of a customisation record, or null
 * when the write is not one (callers then fall back to the generic write line).
 */
export function customisationConsequence(toolName, input) {
	if (!["create_document", "update_document", "delete_document"].includes(toolName)) return null;
	if (!input || typeof input !== "object") return null;
	const fields = flattenInput(input);
	if (!CUSTOMISATION_DOCTYPES.has(fields.doctype)) return null;
	if (toolName === "delete_document") return __("This removes a customisation from your site for everyone");
	const describe = CUSTOMISATION_CONSEQUENCES[fields.doctype];
	return describe ? describe(fields) : null;
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
	if (toolName === "document_action") return documentActionConsequence(input);
	return WRITE_CONSEQUENCES[toolName] || "";
}
