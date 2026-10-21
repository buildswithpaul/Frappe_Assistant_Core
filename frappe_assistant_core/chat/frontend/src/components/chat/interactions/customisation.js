/**
 * What an approval card says about the write it is asking to make.
 *
 * Only tools we are certain write to the ERP get a line. Read-only and dynamic tools
 * (ask_user, get_skill, run_python_code) may not write, and a false "will write" warning
 * trains users to ignore it on calls that do mutate data.
 */

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
	if (toolName === "document_action") return documentActionConsequence(input);
	return WRITE_CONSEQUENCES[toolName] || "";
}
