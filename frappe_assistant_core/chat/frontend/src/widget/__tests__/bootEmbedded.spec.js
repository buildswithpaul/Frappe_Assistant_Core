import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const reply = (message) => ({ ok: true, json: async () => ({ message }) });

// A page with no Desk at all; any read of window.frappe fails the test.
function forbidFrappe() {
	Object.defineProperty(window, "frappe", {
		configurable: true,
		get() {
			throw new Error("window.frappe was touched");
		},
	});
}

describe("bootEmbedded", () => {
	beforeEach(() => {
		vi.resetModules();
		window.csrf_token = "token";
		window.__facWidgetBooted = false;
		forbidFrappe();
	});

	afterEach(() => {
		delete window.frappe;
		window.__facWidgetBooted = false;
	});

	it("checks access over fetch on a page without Desk, and never reads window.frappe", async () => {
		globalThis.fetch = vi.fn(async (url) =>
			reply(url.includes("get_logged_user") ? "agent@example.com" : { can_use: false, show_widget: false })
		);
		const { bootEmbedded } = await import("../main.js");
		await expect(bootEmbedded({ entry: "/x.js", css: [] })).resolves.toBeUndefined();
		expect(fetch.mock.calls.map(([url]) => url).some((url) => url.includes("can_use_faco"))).toBe(true);
	});

	it("mounts nothing for a Guest", async () => {
		globalThis.fetch = vi.fn(async () => reply("Guest"));
		const { bootEmbedded } = await import("../main.js");
		await bootEmbedded({ entry: "/x.js", css: [] });
		expect(fetch).toHaveBeenCalledTimes(1);
		expect(document.getElementById("fac-widget-launcher")).toBeNull();
	});
});
