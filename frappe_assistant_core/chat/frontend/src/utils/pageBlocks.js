/**
 * The tools a FAC Page uses to let people type into records: whether the viewer may change a
 * record, who changed it last, inline editing of a text field or a child table, and a period
 * picker. Bundled with fac.chart and fac.report (pageFacBundle.js), so Desk, the chat panel and a
 * personal page's frame run the same code.
 *
 * Each tool uses only what Desk's frappe and the chat's stand-in both offer: frappe.call,
 * frappe.db.get_doc and frappe.datetime.str_to_user. Saves go through frappe.client, so the
 * server's permission checks decide them; on a personal page each one asks the user first.
 * canWrite only decides whether an edit control is shown.
 */
import { __ } from "@/utils/i18n";

import { makeEditors } from "./pageEditList";

const message = (r) => r?.message;

/** The page tools for a page whose script sees `frappe`. */
export function makeBlocks(frappe) {
	async function canWrite(doctype, name) {
		try {
			const r = await frappe.call({
				method: "frappe.client.has_permission",
				type: "GET",
				args: { doctype, docname: name, perm_type: "write" },
			});
			return Boolean(message(r)?.has_permission);
		} catch {
			return false;
		}
	}

	function updated(doc = {}) {
		if (!doc.modified_by) return "";
		const when = doc.modified ? frappe.datetime.str_to_user(doc.modified) : "";
		return when ? __("Updated by {0} · {1}", [doc.modified_by, when]) : __("Updated by {0}", [doc.modified_by]);
	}

	const notYet = (name) => () => {
		throw new Error(`fac.${name} is not available yet`);
	};

	return { canWrite, updated, ...makeEditors(frappe, canWrite), periodPicker: notYet("periodPicker") };
}
