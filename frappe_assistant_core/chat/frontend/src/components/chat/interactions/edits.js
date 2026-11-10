import { __ } from "@/utils/i18n";

/**
 * Client-side twin of `frappe_assistant_core/utils/edits.py:apply_edits`: the rules must match so
 * the card shows the text the server will store. Each `find` is literal (never a RegExp, and the
 * replacement is spliced in, never passed to String.replace, so `$&` stays text), must match
 * exactly once, and edits apply in order. A field stored with CRLF line endings keeps them: a bare
 * LF in `find` and `replace` is read as CRLF.
 */

const toCrlf = (text) => text.replace(/\r\n/g, "\n").replace(/\n/g, "\r\n");

const isEdit = (edit) =>
	edit !== null &&
	typeof edit === "object" &&
	["field", "find", "replace"].every((key) => typeof edit[key] === "string");

/** The fields a tool input's `edits` touch, each once, in order. */
export function editedFields(input) {
	const edits = Array.isArray(input?.edits) ? input.edits : [];
	return [...new Set(edits.filter(isEdit).map((edit) => edit.field))];
}

function applyOne(value, { field, find, replace }) {
	if (!find) throw new Error(__("'{0}' is empty", [field]));
	if (value.includes("\r\n")) {
		find = toCrlf(find);
		replace = toCrlf(replace);
	}
	const at = value.indexOf(find);
	// Non-overlapping, like Python's str.count: a second match must start after the first ends.
	const again = at === -1 ? -1 : value.indexOf(find, at + find.length);
	if (at === -1 || again !== -1) {
		throw new Error(__("'{0}' matched {1} times in {2}; it must match exactly once.", [find, at === -1 ? 0 : 2, field]));
	}
	return value.slice(0, at) + replace + value.slice(at + find.length);
}

/**
 * Apply `edits` to `current` ({field: stored text}). Returns the new text of each field that
 * applied, the first error, and the fields that failed (an edit after a failed one on the same
 * field is skipped). Never throws.
 */
export function applyEdits(current, edits) {
	const values = {};
	const failedFields = [];
	let error = null;
	const fail = (field, message) => {
		error ??= message;
		if (field !== undefined && !failedFields.includes(field)) failedFields.push(field);
	};

	for (const edit of Array.isArray(edits) ? edits : []) {
		if (!isEdit(edit)) {
			fail(undefined, __("'edits' must be a list of {'field', 'find', 'replace'} objects with text values."));
			continue;
		}
		if (failedFields.includes(edit.field)) continue;
		const stored = edit.field in values ? values[edit.field] : (current?.[edit.field] ?? "");
		if (typeof stored !== "string") {
			fail(edit.field, __("'{0}' is not a text field", [edit.field]));
			continue;
		}
		try {
			values[edit.field] = applyOne(stored, edit);
		} catch (e) {
			fail(edit.field, e.message);
		}
	}
	for (const field of failedFields) delete values[field];
	return { values, error, failedFields };
}
