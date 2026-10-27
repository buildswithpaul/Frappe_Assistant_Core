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

	it("lists every page the user can open over GET", async () => {
		await facPage.listPages();
		expect(getCall).toHaveBeenCalledWith("frappe_assistant_core.api.fac_page.list_pages");
	});

	it("no longer lists pages with a raw get_list", () => {
		expect(facPage.listMine).toBeUndefined();
	});
});
