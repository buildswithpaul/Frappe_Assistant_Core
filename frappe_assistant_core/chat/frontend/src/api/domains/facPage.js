import { getCall } from "../_core";

export const facPage = {
	// `name` is the record name, which for a personal page is not its slug.
	getPage: (name) => getCall("frappe_assistant_core.api.fac_page.get_page", { slug: name }),

	// The permission query limits the list to pages the user may open from here.
	listMine: () =>
		getCall("frappe.client.get_list", {
			doctype: "FAC Page",
			fields: JSON.stringify(["name", "title"]),
			order_by: "modified desc",
			limit_page_length: 20,
		}),
};
