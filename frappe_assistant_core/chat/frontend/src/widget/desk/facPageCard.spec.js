import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";

// Loaded as the Desk page inlines it, with fac_page_draft.js, whose srcdoc builder the preview uses.
const DIR = resolve(import.meta.dirname, "../../../../../assistant_core/page/fac_pages");
const SOURCE = ["fac_page_draft.js", "fac_page_card.js"].map((file) => readFileSync(resolve(DIR, file), "utf-8")).join("\n");
const translate = (text, args = []) => args.reduce((out, arg, i) => out.replace(`{${i}}`, arg), text);
const { fac_page_card, fac_page_delete_message } = new Function(
	"__",
	`${SOURCE}\nreturn { fac_page_card, fac_page_delete_message };`,
)(translate);

const base = {
	name: "payment-tracker-3fa9c1",
	title: "Payment Tracker",
	description: "Overdue invoices by customer",
	visibility: "Only me",
	draft: false,
	modified: "2026-11-11 10:00:00",
	roles: [],
	preview_html: '<div class="mk-card"><span>Due</span><b>0</b></div>',
	preview_style: ".mk-card { color: teal; }",
};
// The four cases list_pages produces: a personal page of a System Manager and of another Desk
// user, and a shared page as a System Manager and as a role holder sees it.
const smPersonal = { ...base, can_manage: true, can_share: true };
const userPersonal = { ...base, can_manage: true, can_share: false };
const smShared = { ...base, visibility: "Shared", roles: ["Sales User"], can_manage: true, can_share: false };
const readerShared = { ...smShared, can_manage: false };

const actions = () => ({ edit: vi.fn(), rename: vi.fn(), share: vi.fn(), remove: vi.fn() });
const card = (page, options = {}) =>
	fac_page_card(page, {
		href: (name) => `/app/fac-pages/${name}`,
		updated: () => "2 days ago",
		kit_css: ".kit{}",
		can_chat: true,
		actions: actions(),
		...options,
	});
const menuItems = (item) => {
	const button = item.querySelector("button.fac-page-index-menu");
	if (!button) return [];
	button.click();
	return [...item.querySelectorAll(".fac-page-index-menu-item")].map((el) => el.textContent);
};

describe("fac_page_card", () => {
	it("shows the title, description, access and when it was updated, linked to the page", () => {
		const item = card(userPersonal);
		const link = item.querySelector("a.fac-page-index-card-link");
		expect(link.getAttribute("href")).toBe("/app/fac-pages/payment-tracker-3fa9c1");
		expect(item.querySelector(".fac-page-index-title").textContent).toBe("Payment Tracker");
		expect(item.querySelector(".fac-page-index-description").textContent).toBe("Overdue invoices by customer");
		expect(item.querySelector(".fac-page-index-context").textContent).toBe("Only you");
		expect(item.querySelector(".fac-page-index-updated").textContent).toBe("Updated 2 days ago");
		expect(link.querySelector("button")).toBeNull();
	});

	it("leaves the description line out when the page has none", () => {
		expect(card({ ...userPersonal, description: "" }).querySelector(".fac-page-index-description")).toBeNull();
	});

	it("offers each action only to someone who may take it", () => {
		expect(menuItems(card(smPersonal))).toEqual(["Edit with FACO", "Rename", "Share", "Delete"]);
		expect(menuItems(card(userPersonal))).toEqual(["Edit with FACO", "Rename", "Delete"]);
		expect(menuItems(card(smShared))).toEqual(["Edit with FACO", "Rename", "Delete"]);
		expect(menuItems(card(readerShared))).toEqual([]);
		expect(card(readerShared).querySelector("button.fac-page-index-menu")).toBeNull();
	});

	it("leaves out the actions that need FACO for someone who cannot chat", () => {
		expect(menuItems(card(smPersonal, { can_chat: false }))).toEqual(["Rename", "Delete"]);
	});

	it("calls each action with its page", () => {
		const acts = actions();
		const item = card(smPersonal, { actions: acts });
		item.querySelector("button.fac-page-index-menu").click();
		for (const el of item.querySelectorAll(".fac-page-index-menu-item")) el.click();
		for (const fn of [acts.edit, acts.rename, acts.share, acts.remove]) expect(fn).toHaveBeenCalledWith(smPersonal);
	});

	it("previews the page's static html in a frame that runs nothing and fetches nothing", () => {
		const frame = card(userPersonal).querySelector(".fac-page-index-preview iframe");
		expect(frame.getAttribute("sandbox")).toBe("");
		expect(frame.getAttribute("loading")).toBe("lazy");
		expect(frame.getAttribute("tabindex")).toBe("-1");
		expect(frame.getAttribute("aria-hidden")).toBe("true");
		expect(frame.srcdoc).toContain('<div class="mk-card"><span>Due</span><b>0</b></div>');
		expect(frame.srcdoc).toContain(".mk-card { color: teal; }");
		expect(frame.srcdoc).toContain("default-src 'none'");
		expect(frame.srcdoc).not.toContain("<script");
	});

	it("shows the title's first letter when the page has no preview", () => {
		const item = card({ ...userPersonal, title: "payment tracker", preview_html: null });
		expect(item.querySelector("iframe")).toBeNull();
		expect(item.querySelector(".fac-page-index-tile").textContent).toBe("P");
	});

	it("sets a page's title and description as text, never as html", () => {
		const item = card({ ...userPersonal, title: '<img src=x onerror="alert(1)">', description: "<b>bold</b>" });
		expect(item.querySelector("img")).toBeNull();
		expect(item.querySelector(".fac-page-index-description b")).toBeNull();
		expect(item.querySelector(".fac-page-index-title").textContent).toBe('<img src=x onerror="alert(1)">');
	});

	it("opens the menu as a keyboard user expects, and closes it with Escape", () => {
		const item = card(smPersonal);
		document.body.append(item);
		const button = item.querySelector("button.fac-page-index-menu");
		expect(button.getAttribute("aria-expanded")).toBe("false");
		button.click();
		expect(button.getAttribute("aria-expanded")).toBe("true");
		const entries = [...item.querySelectorAll(".fac-page-index-menu-item")];
		expect(entries.every((el) => el.tagName === "BUTTON")).toBe(true);
		expect(document.activeElement).toBe(entries[0]);
		item.querySelector(".fac-page-index-menu-list").dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
		expect(item.querySelector(".fac-page-index-menu-list").hidden).toBe(true);
		expect(button.getAttribute("aria-expanded")).toBe("false");
		expect(document.activeElement).toBe(button);
		item.remove();
	});

	it("closes the menu on a click outside it", () => {
		const item = card(smPersonal);
		document.body.append(item);
		item.querySelector("button.fac-page-index-menu").click();
		document.body.click();
		expect(item.querySelector(".fac-page-index-menu-list").hidden).toBe(true);
		item.remove();
	});
});

describe("fac_page_delete_message", () => {
	it("escapes the title, since Desk's confirm dialog renders its message as html", () => {
		const message = fac_page_delete_message('<img src=x onerror="alert(1)">');
		expect(message).not.toContain("<img");
		expect(message).toContain("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;");
	});
});
