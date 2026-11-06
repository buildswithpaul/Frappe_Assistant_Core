import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

// The Desk page inlines this plain script with Frappe's render_include, so the test loads it the same way:
// as source text, evaluated for the function it declares, with Desk's global __.
const SOURCE = readFileSync(
	resolve(import.meta.dirname, "../../../../../assistant_core/page/fac_pages/fac_page_index.js"),
	"utf-8",
);
const translate = (text, args = []) => args.reduce((out, arg, i) => out.replace(`{${i}}`, arg), text);
const fac_page_index = new Function("__", `${SOURCE}\nreturn fac_page_index;`)(translate);

const personal = {
	name: "my-receivables",
	title: "My Receivables",
	visibility: "Only me",
	draft: false,
	modified: "2026-10-27 10:00:00",
	roles: [],
};
const shared = {
	name: "quick-customer",
	title: "Quick Customer",
	visibility: "Shared",
	draft: false,
	modified: "2026-10-27 09:00:00",
	roles: ["Sales User"],
};

const render = (options) =>
	fac_page_index({
		href: (name) => `/app/fac-pages/${name}`,
		updated: () => "2 hours ago",
		...options,
	});
const texts = (root, selector) => [...root.querySelectorAll(selector)].map((el) => el.textContent);

describe("fac_page_index", () => {
	it("groups the user's own pages before the pages shared with them", () => {
		const root = render({ pages: [shared, personal] });
		expect(texts(root, ".fac-page-index-heading")).toEqual(["Your pages · 1", "Shared with you · 1"]);
		expect(texts(root, ".fac-page-index-title")).toEqual(["My Receivables", "Quick Customer"]);
	});

	it("opens each page in Desk", () => {
		const root = render({ pages: [shared] });
		expect(root.querySelector("a.fac-page-index-item").getAttribute("href")).toBe("/app/fac-pages/quick-customer");
	});

	it("says who a shared page is shared with, and when it was updated", () => {
		const root = render({ pages: [{ ...shared, roles: ["Accounts User", "Sales Manager", "Sales User"] }, personal] });
		expect(texts(root, ".fac-page-index-context")).toEqual(["Only you", "Shared with Accounts User, Sales Manager +1"]);
		expect(texts(root, ".fac-page-index-updated")).toEqual(["Updated 2 hours ago", "Updated 2 hours ago"]);
	});

	it("marks a draft as not published", () => {
		const root = render({ pages: [{ ...shared, draft: true }] });
		expect(texts(root, ".fac-page-index-context")).toEqual(["Draft · not published yet, only admins see it"]);
	});

	it("shows only the sections that have pages", () => {
		const root = render({ pages: [shared] });
		expect(texts(root, ".fac-page-index-heading")).toEqual(["Shared with you · 1"]);
	});

	it("says so when there are no pages, instead of a blank screen", () => {
		const root = render({ pages: [] });
		expect(texts(root, ".fac-page-index-empty")).toEqual(["No pages have been shared with you yet."]);
		expect(root.querySelector(".fac-page-index-item")).toBeNull();
	});

	it("links to FAC Chat only when given a chat link", () => {
		expect(render({ pages: [shared] }).querySelector(".fac-page-index-chat")).toBeNull();
		const link = render({ pages: [shared], chat_url: "/copilot/pages" }).querySelector(".fac-page-index-chat");
		expect(link.getAttribute("href")).toBe("/copilot/pages");
	});

	it("sets a page's title as text, never as html", () => {
		const root = render({ pages: [{ ...shared, title: '<img src=x onerror="alert(1)">' }] });
		expect(root.querySelector("img")).toBeNull();
		expect(texts(root, ".fac-page-index-title")).toEqual(['<img src=x onerror="alert(1)">']);
	});
});
