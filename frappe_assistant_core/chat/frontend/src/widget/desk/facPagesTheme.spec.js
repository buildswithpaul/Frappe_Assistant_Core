import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { facPagesSource } from "./facPagesSource";

// The fac-pages Desk page script, run as Desk runs it, in Desk's light or dark theme.
const SOURCE = facPagesSource();

const shared = { title: "Review", html: "<p>Review</p>", style: "", script: "", draft: false, visibility: "Shared" };

let frappe;
let wrapper;
let main;
let frames;

function loadDeskPage(data) {
	main = document.createElement("div");
	document.body.append(main);
	const page_main = { empty: () => ((main.innerHTML = ""), page_main), append: (...els) => (main.append(...els), page_main) };
	frappe = {
		pages: { "fac-pages": {} },
		session: { user: "avery@example.com" },
		csrf_token: "csrf-1",
		ui: { make_app_page: () => ({ main: page_main, set_title: vi.fn(), clear_primary_action: vi.fn(), clear_secondary_action: vi.fn(), set_secondary_action: vi.fn() }) },
		get_route: () => ["fac-pages", "review"],
		call: ({ callback }) => callback({ message: data }),
		// As Frappe's dom.js does: a custom element inside the wrapper holds the shadow root, and the
		// js runs at once as a global script whose only own binding is root_element.
		create_shadow_element: vi.fn((host, html, css, js) => {
			const block = document.createElement("custom-block-abcde");
			host.append(block);
			const root = block.attachShadow({ mode: "open" });
			root.innerHTML = html;
			new Function("ROOT", "frappe", `(function () { let root_element = ROOT; ${js} })();`)(root, frappe);
		}),
	};
	const $ = () => ({ text: (message) => Object.assign(document.createElement("p"), { textContent: message }) });
	new Function("frappe", "__", "$", SOURCE)(frappe, (s) => s, $);
	wrapper = {};
	frappe.pages["fac-pages"].on_page_load(wrapper);
	frappe.pages["fac-pages"].on_page_show(wrapper);
}

const setTheme = (theme) => document.documentElement.setAttribute("data-theme", theme);
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const shadowHost = () => main.querySelector("custom-block-abcde");

beforeEach(() => {
	frames = [];
	window.fac_page_frame_host = {
		createPageFrame: vi.fn((options) => {
			const handle = { options, element: document.createElement("iframe"), dispose: vi.fn(), setTheme: vi.fn() };
			frames.push(handle);
			return handle;
		}),
		fetchTransport: vi.fn(() => ({})),
	};
	vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, text: async () => ".kit{}" })));
});

afterEach(() => {
	document.head.querySelectorAll("script").forEach((s) => s.remove());
	document.documentElement.removeAttribute("data-theme");
	delete window.fac_page_frame_host;
	vi.unstubAllGlobals();
	document.body.innerHTML = "";
});

describe("fac-pages Desk page in Desk's theme", () => {
	it("marks a shared page's shadow host dark before the page's script runs", async () => {
		setTheme("dark");
		loadDeskPage({ ...shared, script: "window.__themeSeen = root_element.host.getAttribute('data-theme');" });
		await vi.waitFor(() => expect(shadowHost()).not.toBeNull());
		expect(window.__themeSeen).toBe("dark");
		delete window.__themeSeen;
	});

	it("follows Desk's theme on a shared page without a script", async () => {
		setTheme("dark");
		loadDeskPage(shared);
		await vi.waitFor(() => expect(shadowHost()?.getAttribute("data-theme")).toBe("dark"));
		setTheme("light");
		await tick();
		expect(shadowHost().getAttribute("data-theme")).toBe("light");
	});

	it("starts a personal page's frame in Desk's theme and tells it of a change", async () => {
		setTheme("dark");
		loadDeskPage({ ...shared, visibility: "Only me", owner_is_me: true });
		document.head.querySelectorAll("script").forEach((s) => s.dispatchEvent(new Event("load")));
		await vi.waitFor(() => expect(frames).toHaveLength(1));
		expect(frames[0].options.theme).toBe("dark");
		setTheme("light");
		await tick();
		expect(frames[0].setTheme).toHaveBeenCalledWith("light");
	});

	it("draws a draft in Desk's theme and redraws it on a change", async () => {
		setTheme("dark");
		loadDeskPage({ ...shared, draft: true });
		await vi.waitFor(() => expect(main.querySelector("iframe")).not.toBeNull());
		expect(main.querySelector("iframe").srcdoc).toContain('<html data-theme="dark">');
		setTheme("light");
		await tick();
		expect(main.querySelector("iframe").srcdoc).toContain('<html data-theme="light">');
	});
});
