/**
 * fac.editList and fac.editText: a FAC Page shows a record's child rows or one of its text fields
 * and lets someone who may change the record edit it in place (pageBlocks.js).
 *
 * A save starts from the record as it is now, read again, so it keeps every field the page does
 * not show, and sends the record's modified time from when the page read it, so Frappe refuses a
 * save over a change someone else made meanwhile. A refused save keeps what the user typed and
 * says why. Every value is set as text.
 */
import { __ } from "@/utils/i18n";

// The severities a badge column colours; any other value is a plain badge.
const SEVERITIES = ["high", "med", "low"];

function el(tag, className, text) {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text !== undefined) node.textContent = text;
	return node;
}

function btn(label, className, onClick) {
	const node = el("button", className, label);
	node.type = "button";
	node.addEventListener("click", onClick);
	return node;
}

function badge(value) {
	const severity = String(value ?? "").toLowerCase();
	return el("span", SEVERITIES.includes(severity) ? `mk-badge mk-sev-${severity}` : "mk-badge", value ?? "");
}

function input(column, value) {
	let node;
	if (column.fieldtype === "Select") {
		node = el("select");
		const options = [...(column.options || [])];
		// A stored value outside the options stays selectable, so saving another field keeps it.
		if (value && !options.includes(value)) options.unshift(value);
		for (const option of options) node.append(el("option", "", option));
	} else {
		node = el(column.fieldtype === "Small Text" ? "textarea" : "input");
	}
	node.value = value ?? "";
	node.dataset.fieldname = column.fieldname;
	node.setAttribute("aria-label", column.label || column.fieldname);
	return node;
}

const failure = (error) => String(error?.userMessage || error?.message || __("This could not be saved."));

export function makeEditors(frappe, canWrite) {
	// The modified time this page last saw for each record. Every list and text on the page shares
	// it, so one block's save does not make another block's look stale; a change by anyone else
	// still leaves it behind the record's, and Frappe refuses that save.
	const seen = new Map();
	const key = (doctype, name) => `${doctype}\u0000${name}`;
	const note = (doctype, name, doc) => {
		if (doc?.modified) seen.set(key(doctype, name), doc.modified);
		return doc;
	};
	const read = async (doctype, name) => {
		const doc = await frappe.db.get_doc(doctype, name);
		if (!seen.has(key(doctype, name))) note(doctype, name, doc);
		return doc;
	};
	const allowed = (options) => (options.canEdit === undefined ? canWrite(options.doctype, options.name) : Boolean(options.canEdit));

	async function editList(root, options) {
		const { doctype, name, table, columns, onSaved, emptyText = __("Nothing yet") } = options;
		const canEdit = await allowed(options);
		let doc = await read(doctype, name);

		function view() {
			root.replaceChildren();
			const rows = doc?.[table] || [];
			if (!rows.length) root.append(el("p", "mk-text", emptyText));
			else {
				const list = el("ul", "mk-list");
				for (const row of rows) {
					const item = el("li");
					for (const column of columns) {
						item.append(column.badge ? badge(row[column.fieldname]) : el("span", "", row[column.fieldname] ?? ""), " ");
					}
					list.append(item);
				}
				root.append(list);
			}
			if (canEdit) root.append(btn(__("Edit"), "mk-btn mk-edit", edit));
		}

		function edit() {
			root.replaceChildren();
			const box = el("div", "mk-edit-rows mk-edit");
			const addRow = (row) => {
				const line = el("div", "mk-edit-row");
				line._row = row;
				for (const column of columns) line.append(input(column, row?.[column.fieldname]));
				line.append(btn(__("Remove"), "mk-btn mk-edit mk-edit-remove", () => line.remove()));
				box.append(line);
			};
			(doc?.[table] || []).forEach(addRow);
			const error = el("p", "mk-edit-error");
			error.hidden = true;
			const save = async () => {
				error.hidden = true;
				const edited = [...box.querySelectorAll(".mk-edit-row")].map((line) => {
					const values = Object.fromEntries(
						[...line.querySelectorAll("[data-fieldname]")].map((field) => [field.dataset.fieldname, field.value]),
					);
					return { line, values };
				});
				try {
					const current = await read(doctype, name);
					// The time the rows on screen were read: Frappe refuses the save if the record
					// changed since, instead of losing or reverting someone else's rows.
					current.modified = seen.get(key(doctype, name)) || doc.modified;
					const stored = new Map((current[table] || []).map((row) => [row.name, row]));
					current[table] = edited
						.filter(({ line, values }) => line._row?.name || Object.values(values).some((value) => value !== ""))
						.map(({ line, values }) => (line._row?.name ? { ...(stored.get(line._row.name) || line._row), ...values } : values));
					const r = await frappe.call({ method: "frappe.client.save", args: { doc: current } });
					doc = note(doctype, name, r?.message) || current;
					view();
					onSaved?.(doc);
				} catch (e) {
					error.textContent = failure(e);
					error.hidden = false;
				}
			};
			root.append(
				box,
				btn(__("Add row"), "mk-btn mk-edit mk-edit-add", () => addRow(null)),
				btn(__("Save"), "mk-btn mk-btn-primary mk-edit", save),
				btn(__("Cancel"), "mk-btn mk-edit", view),
				error,
			);
		}

		view();
		return {
			async reload() {
				doc = note(doctype, name, await frappe.db.get_doc(doctype, name));
				view();
			},
		};
	}

	async function editText(root, options) {
		const { doctype, name, fieldname, multiline = false, onSaved, emptyText = __("Nothing yet") } = options;
		const canEdit = await allowed(options);
		let doc = await read(doctype, name);

		function view() {
			root.replaceChildren(el("div", "mk-text", doc?.[fieldname] || emptyText));
			if (canEdit) root.append(btn(__("Edit"), "mk-btn mk-edit", edit));
		}

		function edit() {
			const field = el(multiline ? "textarea" : "input");
			field.value = doc?.[fieldname] ?? "";
			field.setAttribute("aria-label", fieldname);
			const error = el("p", "mk-edit-error");
			error.hidden = true;
			const save = async () => {
				error.hidden = true;
				try {
					const r = await frappe.call({
						method: "frappe.client.set_value",
						args: { doctype, name, fieldname, value: field.value },
					});
					doc = note(doctype, name, r?.message) || { ...doc, [fieldname]: field.value };
					view();
					onSaved?.(doc);
				} catch (e) {
					error.textContent = failure(e);
					error.hidden = false;
				}
			};
			root.replaceChildren(field, btn(__("Save"), "mk-btn mk-btn-primary mk-edit", save), btn(__("Cancel"), "mk-btn mk-edit", view), error);
		}

		view();
		return {
			async reload() {
				doc = note(doctype, name, await frappe.db.get_doc(doctype, name));
				view();
			},
		};
	}

	return { editList, editText };
}
