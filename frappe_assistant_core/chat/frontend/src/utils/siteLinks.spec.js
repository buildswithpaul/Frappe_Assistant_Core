import { describe, it, expect, afterEach } from "vitest";
import { localizeSiteLink } from "./siteLinks";
import { renderMarkdown } from "./markdown";

// Redmine #34378: FAC Chat installed from 127.0.0.1:8011 got a Desk link on the site's
// host_name (localhost:8000); iOS opened it in an in-app browser with no login.
const SITE = "http://localhost:8000";
const APP = "http://127.0.0.1:8011";

describe("localizeSiteLink", () => {
	it("makes a link to the site relative when the app is open on another address", () => {
		expect(localizeSiteLink(`${SITE}/desk/sales-invoice/new`, SITE, APP)).toBe(
			"/desk/sales-invoice/new"
		);
	});

	it("keeps the query and fragment", () => {
		expect(localizeSiteLink(`${SITE}/app/sales-invoice?status=Draft#top`, SITE, APP)).toBe(
			"/app/sales-invoice?status=Draft#top"
		);
	});

	it("leaves links to other sites alone", () => {
		expect(localizeSiteLink("https://docs.frappe.io/erpnext", SITE, APP)).toBe(
			"https://docs.frappe.io/erpnext"
		);
	});

	it("leaves the link alone when the app is already on the site's address", () => {
		expect(localizeSiteLink(`${SITE}/desk/todo`, SITE, SITE)).toBe(`${SITE}/desk/todo`);
	});

	it("leaves relative links and a missing site address alone", () => {
		expect(localizeSiteLink("/desk/todo", SITE, APP)).toBe("/desk/todo");
		expect(localizeSiteLink(`${SITE}/desk/todo`, undefined, APP)).toBe(`${SITE}/desk/todo`);
	});
});

describe("answer links", () => {
	afterEach(() => {
		delete window.site_url;
	});

	it("open on the address FAC Chat is on", () => {
		// www/copilot.html writes every boot key onto window, site_url among them.
		window.site_url = "http://erp.example.com";
		const html = renderMarkdown("[Open a new Sales Invoice](http://erp.example.com/desk/sales-invoice/new)");
		expect(html).toContain('href="/desk/sales-invoice/new"');
	});
});
