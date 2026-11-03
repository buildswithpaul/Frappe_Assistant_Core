import { getCall } from "../_core";

export const facPage = {
	// `name` is the record name, which for a personal page is not its slug.
	getPage: (name) => getCall("frappe_assistant_core.api.fac_page.get_page", { slug: name }),

	// Every page the user may open: their own first, then shared ones, newest first.
	listPages: () => getCall("frappe_assistant_core.api.fac_page.list_pages"),
};
