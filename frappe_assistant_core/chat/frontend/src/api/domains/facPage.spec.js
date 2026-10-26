import { beforeEach, describe, expect, it, vi } from "vitest";

const getCall = vi.fn();
vi.mock("../_core", () => ({ getCall: (...args) => getCall(...args) }));

import { facPage } from "./facPage";

describe("facPage", () => {
	beforeEach(() => getCall.mockReset().mockResolvedValue({}));

	it("reads a page by its record name over GET", async () => {
		await facPage.getPage("sales-a1b2c3");
		expect(getCall).toHaveBeenCalledWith("frappe_assistant_core.api.fac_page.get_page", { slug: "sales-a1b2c3" });
	});

	it("lists the user's pages newest first, twenty at most", async () => {
		await facPage.listMine();
		expect(getCall).toHaveBeenCalledWith("frappe.client.get_list", {
			doctype: "FAC Page",
			fields: '["name","title"]',
			order_by: "modified desc",
			limit_page_length: 20,
		});
	});
});
