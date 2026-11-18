import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { makePresenter, mountPresentControls, remoteDeck } from "@/utils/pagePresent";

import { facPagesSource } from "./facPagesSource";

// The fac-pages Desk page script, run as Desk runs it, with Present wired to the real presenter.
const SOURCE = facPagesSource();
const SECTIONS =
	'<div class="fac-page-root"><section class="mk-section" data-title="Company">A</section><section class="mk-section" data-title="Finance">B</section></div>';

let frappe;
let wrapper;
let deskPage;

function loadDeskPage(data) {
	const main = {
		el: document.createElement("div"),
		empty: () => main,
		append: (...els) => (main.el.append(...els), main),
		find: (selector) => ({ get: () => main.el.querySelector(selector) }),
	};
	document.body.append(main.el);
	deskPage = {
		main,
		set_title: vi.fn(),
		clear_primary_action: vi.fn(),
		clear_secondary_action: vi.fn(),
		set_secondary_action: vi.fn(),
	};
	frappe = {
		pages: { "fac-pages": {} },
		ui: { make_app_page: () => deskPage },
		get_route: () => ["fac-pages", "review"],
		call: ({ callback }) => callback({ message: data }),
		show_alert: vi.fn(),
		// As Frappe's dom.js does: a custom element inside the wrapper holds the shadow root.
		create_shadow_element: vi.fn((host, html) => {
			const block = document.createElement("custom-block-abcde");
			block.attachShadow({ mode: "open" }).innerHTML = html;
			host.append(block);
		}),
	};
	// Desk's jQuery, as far as the draft view uses it: $('<p>').text(message).
	const $ = () => ({ text: (message) => Object.assign(document.createElement("p"), { textContent: message }) });
	new Function("frappe", "__", "$", SOURCE)(frappe, (s) => s, $);
	wrapper = {};
	frappe.pages["fac-pages"].on_page_load(wrapper);
	frappe.pages["fac-pages"].on_page_show(wrapper);
}

beforeEach(() => {
	window.fac_page_charts = { makePresenter, mountPresentControls, remoteDeck };
	// A draft loads the kit to inline it; the test serves an empty one.
	vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, text: () => Promise.resolve("") })));
});

afterEach(() => {
	document.body.replaceChildren();
	document.head.querySelectorAll("script").forEach((s) => s.remove());
	delete window.fac_page_charts;
	vi.unstubAllGlobals();
});

describe("fac-pages Desk page and Present", () => {
	it("presents a shared page's sections from the header's Present button", async () => {
		loadDeskPage({ title: "Review", html: SECTIONS, style: "", script: "", draft: false, visibility: "Shared" });
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalled());
		const [label, present] = deskPage.set_secondary_action.mock.calls.at(-1);
		expect(label).toBe("Present");
		present();
		// The bundle loads by script tag; the browser fires load once it has run.
		document.head.querySelectorAll("script").forEach((s) => s.dispatchEvent(new Event("load")));
		await vi.waitFor(() => expect(document.querySelector(".fac-present-bar")).not.toBeNull());
		expect(document.querySelector(".fac-present-where").textContent).toBe("1 / 2 · Company");
		const shadow = document.querySelector("custom-block-abcde").shadowRoot;
		expect([...shadow.querySelectorAll(".mk-section")].map((s) => s.classList.contains("fac-present-off"))).toEqual([false, true]);
		expect(frappe.show_alert).not.toHaveBeenCalled();
	});

	const shared = { title: "Review", html: SECTIONS, style: "", script: "", draft: false, visibility: "Shared" };
	const pressPresent = () => {
		deskPage.set_secondary_action.mock.calls.at(-1)[1]();
		document.head.querySelectorAll("script").forEach((s) => s.dispatchEvent(new Event("load")));
	};

	it("starts once however often Present is pressed", async () => {
		loadDeskPage(shared);
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalled());
		pressPresent();
		pressPresent();
		await vi.waitFor(() => expect(document.querySelector(".fac-present-bar")).not.toBeNull());
		await new Promise((resolve) => setTimeout(resolve, 20));
		expect(document.querySelectorAll(".fac-present-bar")).toHaveLength(1);
	});

	it("stops presenting when the user leaves the page", async () => {
		loadDeskPage(shared);
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalled());
		pressPresent();
		await vi.waitFor(() => expect(document.querySelector(".fac-present-bar")).not.toBeNull());
		frappe.pages["fac-pages"].on_page_hide(wrapper);
		await vi.waitFor(() => expect(document.querySelector(".fac-present-bar")).toBeNull());
	});

	it("offers no Present for a draft", () => {
		loadDeskPage({ title: "Review", html: SECTIONS, style: "", script: "", draft: true, visibility: "Shared" });
		expect(deskPage.set_secondary_action).not.toHaveBeenCalled();
	});
});
