import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// The loader is a classic script served from public/, so run its real text as the page would.
const LOADER = readFileSync(resolve(process.cwd(), "../../public/chat/widget/widget_embed.js"), "utf8");
const ENTRY_METHOD = "frappe_assistant_core.chat.api.settings.embed.get_widget_entry";

function runLoader() {
	new Function(LOADER)();
}

describe("widget_embed.js", () => {
	beforeEach(() => {
		globalThis.fetch = vi.fn(async () => ({ ok: false }));
	});
	afterEach(() => delete window.frappe);

	it("starts on an app page with no Frappe globals (Helpdesk)", () => {
		runLoader();
		expect(fetch).toHaveBeenCalledWith(expect.stringContaining(ENTRY_METHOD), expect.anything());
	});

	it("starts on an app page whose shell sets its own frappe.boot (Raven)", () => {
		// raven/www/raven.html sets frappe.boot to Frappe's full boot payload, which carries FAC's
		// own fac_widget key (extend_bootinfo) — but there is no Desk router or widget_loader.js.
		window.frappe = { boot: { sitename: "site", fac_widget: { entry: "/assets/x.js", css: [] } } };
		runLoader();
		expect(fetch).toHaveBeenCalledWith(expect.stringContaining(ENTRY_METHOD), expect.anything());
	});

	it("does nothing when the widget already booted on this page", () => {
		// The server never injects this loader into Desk; booting twice is the only thing to avoid.
		window.__facWidgetBooted = true;
		runLoader();
		expect(fetch).not.toHaveBeenCalled();
		window.__facWidgetBooted = false;
	});
});
