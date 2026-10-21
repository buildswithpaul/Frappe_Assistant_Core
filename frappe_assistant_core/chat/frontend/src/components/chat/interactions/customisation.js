/**
 * What an approval card says about the write it is asking to make.
 *
 * Only tools we are certain write to the ERP get a line. Read-only and dynamic tools
 * (ask_user, get_skill, run_python_code) may not write, and a false "will write" warning
 * trains users to ignore it on calls that do mutate data.
 */

import { __ } from "@/utils/i18n";
import { baseToolName } from "@/utils/toolNames";
import { flattenInput } from "./helpers";
import { isConditionKey } from "./conditions";

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

const startsWithVowel = (word) => /^[aeiou]/i.test(word);

function serverScriptEventSentence(event, doctype) {
	const an = startsWithVowel(doctype);
	switch (event) {
		case "Before Save":
		case "After Save":
			return an
				? __("This code will run every time someone saves an {0}", [doctype])
				: __("This code will run every time someone saves a {0}", [doctype]);
		case "Before Submit":
			return an
				? __("This code will run every time someone submits an {0}", [doctype])
				: __("This code will run every time someone submits a {0}", [doctype]);
		case "Before Cancel":
			return an
				? __("This code will run every time someone cancels an {0}", [doctype])
				: __("This code will run every time someone cancels a {0}", [doctype]);
		default:
			return an
				? __("This code will run every time someone uses an {0}", [doctype])
				: __("This code will run every time someone uses a {0}", [doctype]);
	}
}

function serverScriptConsequence(fields) {
	if (fields.script_type === "API") return __("This code will run on the server when called");
	if (fields.script_type === "Scheduler Event") return __("This code will run on a schedule");
	if (!fields.doctype_event || !fields.reference_doctype) return __("Changes server code that runs on this site");
	return serverScriptEventSentence(fields.doctype_event, fields.reference_doctype);
}

function propertySetterConsequence(fields) {
	const doctype = fields.doc_type;
	if (!doctype) return __("Changes how a field behaves for everyone");
	return startsWithVowel(doctype)
		? __("Changes how an {0} field behaves for everyone", [doctype])
		: __("Changes how a {0} field behaves for everyone", [doctype]);
}

const accessLine = () => __("Changes who can see or do what on this site");
const approvalLine = () => __("Changes how records are approved for everyone");

// One line per doctype, for a create (isUpdate false) or an update. A partial update may omit
// the field that drives the sentence; each line then falls back to a doctype-level sentence
// that stays true, so a customisation never shows the generic ERP write copy.
const CUSTOMISATION_CONSEQUENCES = {
	"Server Script": serverScriptConsequence,
	"Client Script": (f) =>
		f.dt
			? __("This changes how the {0} form behaves in Desk for everyone", [f.dt])
			: __("Changes how a form behaves in Desk for everyone"),
	"Custom Field": (f, isUpdate) => {
		if (isUpdate) return f.dt ? __("Changes a field on every {0}", [f.dt]) : __("Changes a field on a form for everyone");
		return f.dt ? __("Adds a field to every {0}", [f.dt]) : __("Adds a field to a form for everyone");
	},
	"Property Setter": propertySetterConsequence,
	Workflow: (f) =>
		f.document_type
			? __("Changes how {0} records are approved for everyone", [f.document_type])
			: approvalLine(),
	"Workflow State": approvalLine,
	"Workflow Action Master": approvalLine,
	"Print Format": (f) =>
		f.doc_type ? __("Changes how {0} prints", [f.doc_type]) : __("Changes how a document prints"),
	Notification: (f) =>
		f.document_type
			? __("Sends messages automatically when {0} records change", [f.document_type])
			: __("Changes messages that are sent automatically when records change"),
	Report: (f, isUpdate) => {
		if (isUpdate) return f.ref_doctype ? __("Changes a report on {0}", [f.ref_doctype]) : __("Changes a report");
		return f.ref_doctype ? __("Adds a report on {0}", [f.ref_doctype]) : __("Adds a report");
	},
	Role: accessLine,
	"Custom DocPerm": accessLine,
	DocType: () => __("Changes how a kind of record is built for everyone"),
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
	return CUSTOMISATION_CONSEQUENCES[fields.doctype](fields, tool === "update_document");
}

// document_action submits, cancels or amends, so its warning follows the requested action.
const DOCUMENT_ACTION_CONSEQUENCES = {
	submit: () => __("This will submit a record — it becomes immutable"),
	cancel: () => __("This will cancel a submitted record and reverse its accounting and stock entries"),
	amend: () => __("This will create a new draft copy of a cancelled record"),
};

const WRITE_CONSEQUENCES = {
	create_document: () => __("This will write a new record to your ERP"),
	update_document: () => __("This will modify an existing record in your ERP"),
	delete_document: () => __("This will permanently delete a record from your ERP"),
};

function documentActionConsequence(input) {
	const action = input && typeof input === "object" ? String(input.action || "submit") : "";
	const consequence = DOCUMENT_ACTION_CONSEQUENCES[action.trim().toLowerCase()];
	return consequence ? consequence() : __("This will submit, cancel or amend a record in your ERP");
}

export function writeConsequence(toolName, input) {
	const customisation = customisationConsequence(toolName, input);
	if (customisation) return customisation;
	const tool = baseToolName(toolName);
	if (tool === "document_action") return documentActionConsequence(input);
	const consequence = WRITE_CONSEQUENCES[tool];
	return consequence ? consequence() : "";
}

const WRITE_TOOLS = ["create_document", "update_document"];

function writeFields(toolName, input, doctype) {
	if (!WRITE_TOOLS.includes(baseToolName(toolName)) || !input || typeof input !== "object") return null;
	const fields = flattenInput(input);
	return fields.doctype === doctype ? fields : null;
}

const hasText = (value) => typeof value === "string" && value.trim() !== "";

function conditionKeys(fields) {
	return Object.keys(fields).filter((key) => isConditionKey(key) && hasText(fields[key]));
}

/**
 * True when `key` holds a condition expression in this write: a Custom Field's own
 * depends_on-style field, or the value of a Property Setter that sets one.
 */
export function writesCondition(toolName, input, key) {
	const field = writeFields(toolName, input, "Custom Field");
	if (field) return conditionKeys(field).includes(key);
	const setter = writeFields(toolName, input, "Property Setter");
	return Boolean(setter) && key === "value" && isConditionKey(setter.property) && hasText(setter.value);
}

const NO_CONDITION_CHECK = () =>
	__("Checked in the Desk form only — imports, the API and FACO's own writes are not checked.");

/** The caveat a write that sets a field condition always carries, or null for any other write. */
export function conditionNotice(toolName, input) {
	const customField = writeFields(toolName, input, "Custom Field");
	const sets = customField ? conditionKeys(customField).length > 0 : writesCondition(toolName, input, "value");
	return sets ? NO_CONDITION_CHECK() : null;
}

/** Where a new or changed Custom Field will land: null unless the input names the form (dt). */
export function fieldPlacementTarget(toolName, input) {
	const fields = writeFields(toolName, input, "Custom Field");
	if (!fields || !hasText(fields.dt)) return null;
	// An update that does not move the field says nothing about where it sits.
	if (baseToolName(toolName) === "update_document" && !hasText(fields.insert_after)) return null;
	return { doctype: fields.dt, insertAfter: fields.insert_after, fieldtype: fields.fieldtype };
}

// The keys update_document refuses as a rename; flattenInput turns a differing data.name into new_name.
const RENAME_KEYS = ["new_name", "rename"];

// A value names a rename unless it is null, false or blank once stringified (numbers and true count);
// update_document's `_has_rename_value` applies the same rule.
const hasRenameValue = (value) => value != null && value !== false && String(value).trim() !== "";

function renameRequested(toolName, input) {
	if (baseToolName(toolName) !== "update_document" || !input || typeof input !== "object") return false;
	const fields = flattenInput(input);
	return RENAME_KEYS.some((key) => hasRenameValue(fields[key]));
}

/** The keys to hide from the changed-fields list: the rename keys when the update asks for one, else none. */
export function renameKeys(toolName, input) {
	return renameRequested(toolName, input) ? RENAME_KEYS : [];
}

/** The caveat on an update that tries to rename a record, which the tool saves without. */
export function renameNotice(toolName, input) {
	return renameRequested(toolName, input)
		? __("Renaming isn't possible here. Only the other changes will be saved.")
		: null;
}
