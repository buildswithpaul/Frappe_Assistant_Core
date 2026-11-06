/**
 * Code that lives in child rows: a Workflow transition's condition, a Notification recipient's
 * condition, cc and bcc, and a DocType field's eval: conditions and HTML markup. The card shows each
 * such cell in full below its table and, on an update, diffs it against the stored row it stands for.
 */

import { __ } from "@/utils/i18n";
import { CONDITION_KEYS, codeLanguage, formatKey, isChildTable, isEvalExpression } from "./helpers";

// Child-table columns that hold code: a Workflow Transition's condition and a Notification
// Recipient's condition are Python, a recipient's cc and bcc are Jinja templates, and a DocType
// field's eval: conditions and an HTML field's options run on its form. Mirrored in
// chat/api/current_code.py (ROW_CODE_COLUMNS_BY_DOCTYPE).
const ROW_CODE_COLUMNS = {
	Workflow: { transitions: ["condition"] },
	Notification: { recipients: ["condition", "cc", "bcc"] },
	DocType: { fields: [...CONDITION_KEYS, "options"] },
};

// The columns that tell a stored row apart when a write sends rows without a name (replace mode).
// Mirrored in chat/api/current_code.py (ROW_KEY_COLUMNS_BY_DOCTYPE).
const ROW_KEY_COLUMNS = {
	Workflow: { transitions: ["state", "action", "next_state"] },
	Notification: { recipients: ["receiver_by_document_field", "receiver_by_role"] },
	DocType: { fields: ["fieldname"] },
};

/** The child tables of a `doctype` record whose rows hold code. */
export function rowCodeTables(doctype) {
	return Object.keys(ROW_CODE_COLUMNS[doctype] ?? {});
}

const isBlank = (value) => typeof value !== "string" || value.trim() === "";

// Every non-blank cell of a code column is code, except on a DocType's field rows, where only an
// eval: condition is (a bare fieldname reads a field) and options only on an HTML field.
function isCellCode(doctype, column, row) {
	const value = row?.[column];
	if (isBlank(value)) return false;
	if (doctype !== "DocType") return true;
	return column === "options" ? row.fieldtype === "HTML" : isEvalExpression(value);
}

// The stored row a sent row stands for: the one it names, else the one with the same key columns.
function storedRowFor(storedRows, row, keys) {
	if (row.name) return storedRows.find((stored) => stored.name === row.name);
	return storedRows.find((stored) => keys.every((key) => (row[key] ?? "") === (stored[key] ?? "")));
}

// Stored code for the diff: null shows the new code alone (nothing fetched, or a column the user
// may not read), "" diffs a new row as all added.
function previousCode(stored, column) {
	if (stored === undefined) return "";
	return typeof stored[column] === "string" ? stored[column] : null;
}

/**
 * The code a write sets in child rows, one entry per cell that holds code before or after it, so
 * the card shows it in full. `current` is what get_current_code returned (null when not fetched);
 * a table in it lists the stored rows, and each cell then carries `previous` for a diff.
 */
export function rowCodeCells(doctype, fields, current = null) {
	const cells = [];
	for (const [table, columns] of Object.entries(ROW_CODE_COLUMNS[doctype] ?? {})) {
		const rows = isChildTable(fields[table]) ? fields[table] : [];
		const storedRows = Array.isArray(current?.[table]) ? current[table] : null;
		rows.forEach((row, index) => {
			const stored = storedRows ? storedRowFor(storedRows, row, ROW_KEY_COLUMNS[doctype][table]) : undefined;
			const after = { ...stored, ...row };
			for (const column of columns) {
				if (!(column in row)) continue;
				if (!isCellCode(doctype, column, after) && !isCellCode(doctype, column, stored)) continue;
				cells.push({
					key: `${table}.${index}.${column}`,
					label: __("{0}, row {1}: {2}", [formatKey(table), index + 1, formatKey(column)]),
					code: typeof row[column] === "string" ? row[column] : "",
					language: codeLanguage(column, doctype),
					previous: storedRows ? previousCode(stored, column) : null,
				});
			}
		});
	}
	return cells;
}

/**
 * A child table's rows as its table shows them: the cells shown as code (`cells`, from
 * rowCodeCells) and blank code cells are left out, so code shows once, in full, below the table.
 */
export function rowsWithoutCode(doctype, table, rows, cells) {
	const columns = ROW_CODE_COLUMNS[doctype]?.[table] ?? [];
	if (!columns.length) return rows;
	const shown = new Set(cells.map((cell) => cell.key));
	return rows.map((row, index) =>
		Object.fromEntries(
			Object.entries(row).filter(
				([key, value]) => !columns.includes(key) || (!shown.has(`${table}.${index}.${key}`) && !isBlank(value)),
			),
		),
	);
}
