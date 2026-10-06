import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createLauncherView } from "./view.js";
import { mirrorDeskTheme } from "./theme.js";
import { parseShortcut, bindShortcut } from "./shortcut.js";
import { applyDiagnosticsSwitch } from "./access.js";
import { setupAutofade } from "./autofade.js";

describe("launcher view", () => {
	beforeEach(() => (document.body.innerHTML = ""));

	it("renders the robot inside its own shadow root, not in the page", () => {
		const view = createLauncherView(document);
		expect(document.querySelector(".faco-robot")).toBeNull();
		expect(view.host.shadowRoot.querySelector(".faco-toggle-btn .faco-robot")).not.toBeNull();
	});

	it("mirrors mood, open state, attention and the spotlight dot onto the markup", () => {
		const view = createLauncherView(document);
		view.setMood("thinking");
		view.setOpen(true);
		view.setAttention(true);
		view.setDot(true);
		expect(view.robot.dataset.mood).toBe("thinking");
		expect(view.widgetEl.classList.contains("faco-open")).toBe(true);
		expect(view.widgetEl.classList.contains("faco-awaiting-approval")).toBe(true);
		expect(view.host.shadowRoot.querySelector(".faco-spotlight-dot")).not.toBeNull();
	});

	it("removes the spotlight dot when it is no longer pending", () => {
		const view = createLauncherView(document);
		view.setDot(true);
		view.setDot(false);
		expect(view.host.shadowRoot.querySelector(".faco-spotlight-dot")).toBeNull();
	});
});

describe("theme mirror", () => {
	it("copies Desk's theme now and follows a later html[data-theme] change", async () => {
		document.documentElement.setAttribute("data-theme", "light");
		const host = document.createElement("div");
		const stop = mirrorDeskTheme(host);
		expect(host.getAttribute("data-theme")).toBe("light");
		document.documentElement.setAttribute("data-theme", "dark");
		await new Promise((r) => setTimeout(r, 0));
		expect(host.getAttribute("data-theme")).toBe("dark");
		stop();
	});
});

describe("keyboard shortcut", () => {
	it("parses the stored preference format", () => {
		expect(parseShortcut("Ctrl+Shift+K")).toEqual({ key: "k", ctrl: true, shift: true, alt: false });
	});

	it("fires on the exact chord and not when an unnamed modifier is also held", () => {
		const fire = vi.fn();
		const stop = bindShortcut("Ctrl+K", fire);
		document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
		expect(fire).toHaveBeenCalledTimes(1);
		document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true, shiftKey: true }));
		expect(fire).toHaveBeenCalledTimes(1);
		stop();
	});
});

describe("diagnostics kill switch", () => {
	it("writes the operator's decision exactly once, and only when the field came back", () => {
		window.FACODiagnostics = { setEnabled: vi.fn() };
		applyDiagnosticsSwitch({ enable_browser_diagnostics: false });
		expect(window.FACODiagnostics.setEnabled).toHaveBeenCalledWith(false, true);
		window.FACODiagnostics.setEnabled.mockClear();
		applyDiagnosticsSwitch({});
		expect(window.FACODiagnostics.setEnabled).toHaveBeenCalledWith(true, false);
	});
});

describe("autofade", () => {
	it("never fades below laptop width", () => {
		window.innerWidth = 800;
		const el = document.createElement("div");
		setupAutofade(el, { bootGraceMs: 0 });
		window.dispatchEvent(new Event("scroll"));
		expect(el.classList.contains("faco-fade")).toBe(false);
	});

	it("fades at laptop width and restores after idle", async () => {
		window.innerWidth = 1280;
		const el = document.createElement("div");
		setupAutofade(el, { bootGraceMs: 0, idleMs: 10 });
		window.dispatchEvent(new Event("scroll"));
		expect(el.classList.contains("faco-fade")).toBe(true);
		await new Promise((r) => setTimeout(r, 30));
		expect(el.classList.contains("faco-fade")).toBe(false);
	});
});

describe("boot", () => {
	let startBrowserTools;
	let boot;

	beforeEach(async () => {
		vi.resetModules();
		document.body.innerHTML = "";
		delete window.__facWidgetBooted;
		startBrowserTools = vi.fn();
		vi.doMock("../desk/browserTools.js", () => ({ startBrowserTools }));
		vi.doMock("../desk/session.js", () => ({
			resolveWidgetSession: async () => ({ session_id: "s1", restored: false }),
			startClaimResponder: () => () => {},
		}));
		vi.doMock("./panelLoader.js", () => ({ ensurePanel: async () => ({ open() {}, close() {} }) }));
		window.frappe = {
			session: { user: "u@x.com" },
			get_route: () => ["Form"],
			call: vi.fn(async ({ method }) => {
				if (method.endsWith("can_use_faco")) return { message: { show_widget: true, can_use: false } };
				if (method.endsWith("get_widget_settings")) {
					return { message: { privacy: { enable_dom_extraction: true, enable_browser_diagnostics: true } } };
				}
				return { message: null };
			}),
		};
		({ boot } = await import("../main.js"));
	});

	afterEach(() => {
		vi.doUnmock("../desk/browserTools.js");
		vi.doUnmock("../desk/session.js");
		vi.doUnmock("./panelLoader.js");
		delete window.frappe;
	});

	it("hands the browser tools the operator's privacy settings fetched at boot", async () => {
		await boot({ entry: "", css: [] });
		const { getWidgetSettings } = startBrowserTools.mock.calls[0][0];
		expect(getWidgetSettings()).toEqual({
			privacy: { enable_dom_extraction: true, enable_browser_diagnostics: true },
		});
	});

	it("fails closed on DOM extraction when the settings call fails", async () => {
		const original = window.frappe.call;
		window.frappe.call = vi.fn(async (args) => {
			if (args.method.endsWith("get_widget_settings")) throw new Error("boom");
			return original(args);
		});
				await boot({ entry: "", css: [] });
		const { getWidgetSettings } = startBrowserTools.mock.calls[0][0];
		expect(getWidgetSettings().privacy.enable_dom_extraction).toBe(false);
	});
});
