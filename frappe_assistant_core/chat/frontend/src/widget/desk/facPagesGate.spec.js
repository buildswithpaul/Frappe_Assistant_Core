import { beforeEach, describe, expect, it, vi } from "vitest";

import { HELD_HTML, expectNothingRuns } from "@/utils/__tests__/heldHtmlCases";
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
	const page_main = { empty: () => ((main.innerHTML = ""), page_main), append: (...els) => main.append(...els) };
	frappe = {
		pages: { "fac-pages": {} },
		session: { user: USER },
		ui: { make_app_page: () => ({ main: page_main, set_title: vi.fn() }) },
		get_route: () => ["fac-pages", NAME],
		call: ({ callback }) => callback({ message: data }),
		create_shadow_element: vi.fn(),
	};
	// Desk's jQuery, as far as the draft view uses it: $(html).text(message).
	const $ = () => ({ text: (message) => Object.assign(document.createElement("p"), { textContent: message }) });
	new Function("frappe", "__", "$", SOURCE)(frappe, (s) => s, $);
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
		expect(diff.childElementCount).toBe(0);
		bar().querySelector(".fac-page-review-toggle").click();
		expect(diff.hidden).toBe(false);
		expect([...diff.children].map((line) => line.textContent)).toEqual([`- ${SCRIPT}`, `+ ${SCRIPT_V2}`]);
	});

	it("runs nothing from a held page's html, and keeps its forms and buttons", async () => {
		// get_page serves a personal page's html through an allowlist; this is the host's own second line.
		await show(personal({ html: HELD_HTML }));
		const root = document.createElement("div");
		root.innerHTML = frappe.create_shadow_element.mock.calls.at(-1)[1];
		expectNothingRuns(root);
	});

	it("shows a response that does not say it is published as a draft, running nothing", async () => {
		const { draft, ...unmarked } = personal({ visibility: "Shared" });
		loadDeskPage(unmarked);
		frappe.pages["fac-pages"].on_page_show(wrapper);
		await vi.waitFor(() => expect(main.querySelector("iframe.fac-page-draft-frame")).not.toBeNull());
		expect(main.querySelector("iframe").getAttribute("sandbox")).toBe("");
		expect(frappe.create_shadow_element).not.toHaveBeenCalled();
	});

	it("contains the page in a box outside its shadow host, below the review bar", async () => {
		await show(personal());
		const host = frappe.create_shadow_element.mock.calls.at(-1)[0];
		const frame = host.parentElement;
		const box = getComputedStyle(frame);
		expect(box.contain).toMatch(/\blayout\b/);
		expect(box.contain).toMatch(/\bpaint\b/);
		expect(box.isolation).toBe("isolate");
		expect(box.overflow).toBe("clip");
		expect(frame.parentElement).toBe(main);
		expect(frame.contains(bar())).toBe(false);
	});

	it("never holds a Shared page", async () => {
		await show(personal({ visibility: "Shared" }));
		expect(bar()).toBeNull();
		expect(shownText()).toBe("ran v1");
	});
});
