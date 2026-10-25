import { beforeEach, describe, expect, it, vi } from "vitest";

import { fireInlineHandlers } from "@/utils/__tests__/inlineHandlers";
import { fac_page_approve_script, fac_page_approved_script } from "@/utils/facPageApproval";

import { facPagesSource } from "./facPagesSource";

// The fac-pages Desk page script, run as Desk runs it: a plain script with frappe and __ global.
const SOURCE = facPagesSource();
const USER = "avery@example.com";
const NAME = "sales-a1b2c3";
const SCRIPT = "root_element.querySelector('p').textContent = 'ran v1';";
const SCRIPT_V2 = "root_element.querySelector('p').textContent = 'ran v2';";

const personal = (extra = {}) => ({
	title: "Sales",
	html: "<p>Sales</p>",
	style: "",
	script: SCRIPT,
	draft: false,
	visibility: "Only me",
	owner_is_me: true,
	...extra,
});

let frappe;
let wrapper;
let main;

function loadDeskPage(data) {
	main = document.createElement("div");
	const page_main = { empty: () => ((main.innerHTML = ""), page_main), append: (el) => main.append(el) };
	frappe = {
		pages: { "fac-pages": {} },
		session: { user: USER },
		ui: { make_app_page: () => ({ main: page_main, set_title: vi.fn() }) },
		get_route: () => ["fac-pages", NAME],
		call: ({ callback }) => callback({ message: data }),
		create_shadow_element: vi.fn(),
	};
	new Function("frappe", "__", "$", SOURCE)(frappe, (s) => s, vi.fn());
	wrapper = {};
	frappe.pages["fac-pages"].on_page_load(wrapper);
}

// What the page shows once create_shadow_element has run the script it was given, as Desk does.
function shownText() {
	const [, html, , js] = frappe.create_shadow_element.mock.calls.at(-1);
	const root = document.createElement("div");
	root.innerHTML = html;
	new Function("ROOT", "frappe", `(function () { let root_element = ROOT; ${js} })();`)(root, frappe);
	return root.querySelector("p").textContent;
}

async function show(data, times = 1) {
	loadDeskPage(data);
	frappe.pages["fac-pages"].on_page_show(wrapper);
	await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledTimes(times));
}

const bar = () => main.querySelector(".fac-page-review");

beforeEach(() => window.localStorage.clear());

describe("fac-pages Desk page: code FACO writes runs only after the user has seen it", () => {
	it("asks on first open, and draws the html without running the script", async () => {
		await show(personal());
		expect(bar().querySelector(".fac-page-review-message").textContent).toBe("This page has code FACO wrote.");
		expect(shownText()).toBe("Sales");
	});

	it("runs the script once Run new version is clicked, and stores it where the chat reads it", async () => {
		await show(personal());
		bar().querySelector(".fac-page-review-run").click();
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledTimes(2));
		expect(shownText()).toBe("ran v1");
		expect(bar()).toBeNull();
		expect(fac_page_approved_script(USER, NAME).script).toBe(SCRIPT);
	});

	it("runs a script approved in the chat panel, which shares the key and the origin", async () => {
		await fac_page_approve_script(USER, NAME, SCRIPT);
		await show(personal({ html: "<p>Sales</p><i>new html</i>" }));
		expect(bar()).toBeNull();
		expect(shownText()).toBe("ran v1");
	});

	it("holds a changed script, and shows the change from View changes", async () => {
		await fac_page_approve_script(USER, NAME, SCRIPT);
		await show(personal({ script: SCRIPT_V2 }));
		expect(bar().querySelector(".fac-page-review-message").textContent).toBe("FACO changed this page's code.");
		expect(shownText()).toBe("Sales");
		const diff = bar().querySelector(".fac-page-review-diff");
		expect(diff.hidden).toBe(true);
		bar().querySelector(".fac-page-review-toggle").click();
		expect(diff.hidden).toBe(false);
		expect([...diff.children].map((line) => line.textContent)).toEqual([`- ${SCRIPT}`, `+ ${SCRIPT_V2}`]);
	});

	it("runs no inline code from a held page's html, and keeps its forms and buttons", async () => {
		// get_page strips these from a personal page's html; this is the host's own second line.
		const html =
			'<p>Sales</p><img src="x" onerror="window.__deskInlineRan = 1"><svg onload="window.__deskInlineRan = 2"></svg>' +
			'<a class="go" href=" java\tscript:window.__deskInlineRan = 3">go</a><iframe src="https://evil.example"></iframe>' +
			'<form class="mk-form"><input name="q"><button type="button">Go</button></form>';
		await show(personal({ html }));
		const root = document.createElement("div");
		root.innerHTML = frappe.create_shadow_element.mock.calls.at(-1)[1];
		fireInlineHandlers(root, "error");
		fireInlineHandlers(root, "load");
		expect(window.__deskInlineRan).toBeUndefined();
		expect(root.querySelector(".go").getAttribute("href")).toBeNull();
		expect(root.querySelector("iframe")).toBeNull();
		expect(root.querySelector("form.mk-form input[name=q]")).not.toBeNull();
		expect(root.querySelector("form.mk-form button")).not.toBeNull();
	});

	it("never holds a Shared page", async () => {
		await show(personal({ visibility: "Shared" }));
		expect(bar()).toBeNull();
		expect(shownText()).toBe("ran v1");
	});
});
