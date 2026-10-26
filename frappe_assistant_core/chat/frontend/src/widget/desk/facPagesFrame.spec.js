import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { facPagesSource } from "./facPagesSource";

// The fac-pages Desk page script, run as Desk runs it: a plain script with frappe and __ global.
const SOURCE = facPagesSource();
const HOST_SRC = "/assets/frappe_assistant_core/js/fac_page_frame_host.js?v=build-7";

const personal = (extra = {}) => ({
	title: "Sales",
	html: "<p>Sales</p>",
	style: "",
	script: "root_element.textContent = 'ran';",
	draft: false,
	visibility: "Only me",
	owner_is_me: true,
	...extra,
});

let frappe;
let wrapper;
let main;
let created;

function loadDeskPage(data) {
	main = document.createElement("div");
	document.body.append(main);
	const page_main = { empty: () => ((main.innerHTML = ""), page_main), append: (...els) => main.append(...els) };
	frappe = {
		pages: { "fac-pages": {} },
		session: { user: "avery@example.com" },
		csrf_token: "csrf-1",
		ui: { make_app_page: () => ({ main: page_main, set_title: vi.fn() }) },
		get_route: () => ["fac-pages", "sales-a1b2c3"],
		call: ({ callback }) => callback({ message: data }),
		create_shadow_element: vi.fn(),
	};
	new Function("frappe", "__", "$", SOURCE)(frappe, (s) => s, vi.fn());
	wrapper = {};
	frappe.pages["fac-pages"].on_page_load(wrapper);
}

const show = () => frappe.pages["fac-pages"].on_page_show(wrapper);
const hostScripts = () => [...document.head.querySelectorAll("script")].filter((s) => s.src.includes("fac_page_frame_host"));

beforeEach(() => {
	// jsdom lays nothing out, so it has no scrollIntoView; a browser does.
	Element.prototype.scrollIntoView = vi.fn();
	window._version_number = "build-7";
	created = [];
	window.fac_page_frame_host = {
		createPageFrame: vi.fn((options) => {
			const handle = { options, element: document.createElement("iframe"), dispose: vi.fn() };
			created.push(handle);
			return handle;
		}),
		fetchTransport: vi.fn((getCsrf) => ({ csrf: getCsrf() })),
	};
	vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, text: async () => ".kit{}" })));
});

afterEach(() => {
	hostScripts().forEach((s) => s.remove());
	delete window.fac_page_frame_host;
	delete window._version_number;
	vi.unstubAllGlobals();
	delete Element.prototype.scrollIntoView;
	document.body.innerHTML = "";
});

async function showPersonal(data = personal()) {
	loadDeskPage(data);
	show();
	// jsdom fetches no script; the browser fires load once the bundle has run.
	hostScripts().at(-1)?.dispatchEvent(new Event("load"));
	await vi.waitFor(() => expect(created.length).toBeGreaterThan(0));
	return created.at(-1);
}

describe("fac-pages Desk page and a personal page", () => {
	it("runs a personal page at once in the frame, never in Desk itself", async () => {
		const handle = await showPersonal();
		expect(hostScripts().map((s) => s.getAttribute("src"))).toEqual([HOST_SRC]);
		expect(handle.options.page.script).toBe("root_element.textContent = 'ran';");
		expect(handle.options.kitCss).toBe(".kit{}");
		expect(handle.options.user).toBe("avery@example.com");
		expect(handle.options.transport).toEqual({ csrf: "csrf-1" });
		expect(main.contains(handle.element)).toBe(true);
		expect(frappe.create_shadow_element).not.toHaveBeenCalled();
		expect(main.textContent).not.toContain("Run new version");
	});

	it("runs a page whose visibility is missing in the frame too", async () => {
		const { visibility, ...unmarked } = personal();
		await showPersonal(unmarked);
		expect(frappe.create_shadow_element).not.toHaveBeenCalled();
	});

	it("runs a Shared page in Desk, as before", async () => {
		loadDeskPage(personal({ visibility: "Shared", script: "" }));
		show();
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledOnce());
		expect(window.fac_page_frame_host.createPageFrame).not.toHaveBeenCalled();
	});

	it("asks before each call one at a time, listing its fields, and answers with the user's choice", async () => {
		const handle = await showPersonal();
		expect(handle.options.pageName).toBe("sales-a1b2c3");
		const first = handle.options.askUser({
			message: "This page wants to update ToDo TD-1.",
			fields: [["status", "Closed"]],
			trustable: false,
		});
		const second = handle.options.askUser({ message: "This page wants to run my_app.api.feed.", fields: [], trustable: true });
		await vi.waitFor(() => expect(main.querySelectorAll(".fac-page-write-prompt")).toHaveLength(1));
		expect(main.querySelector(".fac-page-write-message").textContent).toBe("This page wants to update ToDo TD-1.");
		expect(main.querySelector(".fac-page-write-fields").textContent).toBe("statusClosed");
		expect(main.querySelector(".fac-page-write-trust")).toBeNull();
		main.querySelector(".fac-page-write-allow").click();
		expect(await first).toBe("once");
		await vi.waitFor(() =>
			expect(main.querySelector(".fac-page-write-message")?.textContent).toBe("This page wants to run my_app.api.feed."),
		);
		main.querySelector(".fac-page-write-trust").click();
		expect(await second).toBe("page");
		expect(main.querySelector(".fac-page-write-prompt")).toBeNull();
	});

	it("refuses waiting changes and disposes the frame when the user moves on", async () => {
		const handle = await showPersonal();
		const pending = handle.options.askUser({ message: "This page wants to delete ToDo TD-1.", fields: [], trustable: false });
		await vi.waitFor(() => expect(main.querySelector(".fac-page-write-prompt")).not.toBeNull());
		show();
		expect(await pending).toBe(false);
		expect(handle.dispose).toHaveBeenCalled();
	});

	it("grows the frame with the page", async () => {
		const handle = await showPersonal();
		handle.options.onHeight(900);
		expect(handle.element.style.height).toBe("900px");
	});
});
