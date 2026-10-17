import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const json = (message) => ({ ok: true, json: async () => ({ message }) });

async function loadSpaHost(csrf = "token") {
	// _core.js reads the CSRF token once, at import, as on a real page load.
	vi.resetModules();
	window.csrf_token = csrf;
	return (await import("./spaHost.js")).spaHost;
}

describe("getHost", () => {
	it("is Desk unless the embed boot chose another host", async () => {
		vi.resetModules();
		const { getHost, setHost } = await import("./index.js");
		const { deskHost } = await import("./deskHost.js");
		expect(getHost()).toBe(deskHost);
		const other = { name: "other" };
		setHost(other);
		expect(getHost()).toBe(other);
		setHost(null);
		expect(getHost()).toBe(deskHost);
	});
});

describe("deskHost", () => {
	afterEach(() => delete window.frappe);

	it("calls through frappe.call and hides on the full-page assistant", async () => {
		const { deskHost } = await import("./deskHost.js");
		window.frappe = { call: vi.fn(async () => ({ message: 1 })), get_route: () => ["faco-assistant"] };
		await expect(deskHost.call("m.x", { a: 1 })).resolves.toEqual({ message: 1 });
		expect(window.frappe.call).toHaveBeenCalledWith({ method: "m.x", type: "GET", args: { a: 1 } });
		expect(deskHost.isHiddenRoute()).toBe(true);
		// Desk answers page questions with its browser tools, so nothing rides on the message.
		expect(deskHost.sendContext()).toBeNull();
	});
});

describe("spaHost", () => {
	beforeEach(() => {
		delete window.frappe;
		globalThis.fetch = vi.fn();
	});

	it("has no browser tools, no Desk realtime and a general page context", async () => {
		const spaHost = await loadSpaHost();
		expect(spaHost.clientType).toBe("spa");
		expect(spaHost.browserTools).toBe(false);
		expect(spaHost.realtime()).toBeNull();
		expect(spaHost.detectContext()).toEqual({ type: "General" });
	});

	it("calls GET and POST methods with fetch and answers like frappe.call", async () => {
		const spaHost = await loadSpaHost();
		fetch.mockResolvedValueOnce(json({ ok: 1 })).mockResolvedValueOnce(json({ saved: 1 }));
		await expect(spaHost.call("m.get", { a: 1 })).resolves.toEqual({ message: { ok: 1 } });
		expect(fetch.mock.calls[0][0]).toBe("/api/method/m.get?a=1");
		await expect(spaHost.call("m.post", { b: 2 }, "POST")).resolves.toEqual({ message: { saved: 1 } });
		expect(fetch.mock.calls[1][1].method).toBe("POST");
		expect(fetch.mock.calls[1][1].headers["X-Frappe-CSRF-Token"]).toBe("token");
	});

	it("knows the logged-in user after init, and refuses a Guest or a page without a CSRF token", async () => {
		let spaHost = await loadSpaHost();
		fetch.mockResolvedValueOnce(json("agent@example.com"));
		await expect(spaHost.init()).resolves.toBe(true);
		expect(spaHost.user()).toBe("agent@example.com");

		spaHost = await loadSpaHost();
		fetch.mockResolvedValueOnce(json("Guest"));
		await expect(spaHost.init()).resolves.toBe(false);

		spaHost = await loadSpaHost("");
		await expect(spaHost.init()).resolves.toBe(false);
		expect(fetch).toHaveBeenCalledTimes(2);
	});

	it("hears the app's own pushState and back/forward, and restores history when unsubscribed", async () => {
		const spaHost = await loadSpaHost();
		const original = window.history.pushState;
		const seen = vi.fn();
		const stop = spaHost.onRouteChange(seen);
		window.history.pushState({}, "", "/helpdesk/tickets/1");
		expect(window.location.pathname).toBe("/helpdesk/tickets/1");
		window.dispatchEvent(new PopStateEvent("popstate"));
		expect(seen).toHaveBeenCalledTimes(2);
		stop();
		expect(window.history.pushState).toBe(original);
	});

	it("sends the current page's path with each message", async () => {
		const spaHost = await loadSpaHost();
		window.history.replaceState({}, "", "/helpdesk/tickets/3059?tab=activity");
		expect(spaHost.sendContext()).toEqual({ type: "app_page", path: "/helpdesk/tickets/3059" });
	});

	it("opens a Desk link in a new tab instead of leaving the app", async () => {
		const spaHost = await loadSpaHost();
		const open = vi.spyOn(window, "open").mockImplementation(() => null);
		spaHost.openDeskRoute(["Form", "ToDo", "1"], "/app/todo/1");
		expect(open).toHaveBeenCalledWith("/app/todo/1", "_blank", "noopener");
		open.mockRestore();
	});
});

describe("deskHost.onContextChange", () => {
	afterEach(() => {
		delete window.frappe;
		delete window.jQuery;
		vi.useRealTimers();
	});

	it("fires once per navigation, shares one Desk registration, and stops after unsubscribe", async () => {
		vi.useFakeTimers();
		const { deskHost } = await import("./deskHost.js");
		const handlers = {};
		window.jQuery = () => ({ on: (e, fn) => (handlers[e] = fn), off: vi.fn() });
		const routerOn = vi.fn();
		window.frappe = { router: { on: routerOn, off: vi.fn() } };
		const first = vi.fn();
		const second = vi.fn();
		const stopFirst = deskHost.onContextChange(first);
		deskHost.onContextChange(second);
		expect(routerOn).toHaveBeenCalledTimes(1);
		routerOn.mock.calls[0][1]();
		handlers["form-refresh"]();
		vi.advanceTimersByTime(100);
		expect(first).toHaveBeenCalledTimes(1);
		expect(second).toHaveBeenCalledTimes(1);
		stopFirst();
		handlers["form-refresh"]();
		vi.advanceTimersByTime(100);
		expect(first).toHaveBeenCalledTimes(1);
		expect(second).toHaveBeenCalledTimes(2);
	});

	it("is inert on the embedding page", async () => {
		const spaHost = await loadSpaHost();
		expect(spaHost.onContextChange(() => {})()).toBeUndefined();
	});
});
