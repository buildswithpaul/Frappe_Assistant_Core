import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createLauncherView } from "./view.js";
import { mirrorDeskTheme } from "./theme.js";
import { parseShortcut, bindShortcut } from "./shortcut.js";
import { applyDiagnosticsSwitch } from "./access.js";
import { setupAutofade } from "./autofade.js";
import { startTooltips } from "./tooltips.js";

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
	it("maps the access field to setEnabled arguments, persisting only when the field came back", () => {
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

describe("tooltips", () => {
	it("stop() hides a tooltip that is showing", () => {
		document.body.innerHTML = "";
		const view = createLauncherView(document);
		view.tooltip.classList.add("faco-show");
		const stop = startTooltips(view, () => false);
		stop();
		expect(view.tooltip.classList.contains("faco-show")).toBe(false);
	});
});

describe("boot", () => {
	let startBrowserTools, ensurePanel, panel, startTooltips, stopTooltips, access, settingsReply, pending;
	let boot;

	const callImpl = async ({ method }) => {
		if (method.endsWith("can_use_faco")) {
			if (access instanceof Error) throw access;
			return { message: access };
		}
		if (method.endsWith("get_widget_settings")) {
			if (settingsReply instanceof Error) throw settingsReply;
			return { message: settingsReply };
		}
		if (method.endsWith("get_pending_interrupt")) return { message: pending };
		return { message: null };
	};

	beforeEach(async () => {
		vi.resetModules();
		document.body.innerHTML = "";
		delete window.__facWidgetBooted;
		access = { show_widget: true, can_use: false };
		settingsReply = { privacy: { enable_dom_extraction: true, enable_browser_diagnostics: true } };
		pending = { pending: false };
		startBrowserTools = vi.fn();
		panel = { open: vi.fn(), close: vi.fn() };
		ensurePanel = vi.fn(async () => panel);
		stopTooltips = vi.fn();
		startTooltips = vi.fn(() => stopTooltips);
		vi.doMock("../desk/browserTools.js", () => ({ startBrowserTools }));
		vi.doMock("../desk/session.js", () => ({
			resolveWidgetSession: async () => ({ session_id: "s1", restored: true }),
			startClaimResponder: () => () => {},
		}));
		vi.doMock("./panelLoader.js", () => ({ ensurePanel }));
		vi.doMock("./tooltips.js", () => ({ startTooltips }));
		window.FACODiagnostics = { setEnabled: vi.fn() };
		window.frappe = {
			session: { user: "u@x.com" },
			get_route: () => ["Form"],
			call: vi.fn(callImpl),
		};
		({ boot } = await import("../main.js"));
	});

	afterEach(() => {
		vi.doUnmock("../desk/browserTools.js");
		vi.doUnmock("../desk/session.js");
		vi.doUnmock("./panelLoader.js");
		vi.doUnmock("./tooltips.js");
		delete window.frappe;
		delete window.FACODiagnostics;
	});

	const settings = () => startBrowserTools.mock.calls[0][0].getWidgetSettings();
	const bootAndGetBridge = async () => {
		await boot({ entry: "", css: [] });
		return (await import("../bridge.js")).bridge;
	};

	it("hands the browser tools the operator's privacy settings fetched at boot", async () => {
		await boot({ entry: "", css: [] });
		expect(settings()).toEqual({
			privacy: { enable_dom_extraction: true, enable_browser_diagnostics: true },
		});
	});

	it("fails closed on DOM extraction when the settings call fails", async () => {
		settingsReply = new Error("boom");
		await boot({ entry: "", css: [] });
		expect(settings().privacy.enable_dom_extraction).toBe(false);
	});

	it("fails closed when the server's fallback answers without a privacy block", async () => {
		// get_widget_settings' except-branch returns 200 with button/window/messages only.
		settingsReply = { button: {}, window: {}, messages: {}, custom_css: "" };
		await boot({ entry: "", css: [] });
		expect(settings().privacy.enable_dom_extraction).toBe(false);
	});

	it("does not touch the panel on Desk refresh when a conversation was restored but nothing is pending", async () => {
		access = { show_widget: true, can_use: true };
		await boot({ entry: "", css: [] });
		expect(ensurePanel).not.toHaveBeenCalled();
		const root = document.getElementById("fac-widget-launcher").shadowRoot;
		expect(root.querySelector(".faco-widget").classList.contains("faco-open")).toBe(false);
	});

	it("opens the panel exactly once for a pause that survived a reload", async () => {
		access = { show_widget: true, can_use: true };
		pending = { pending: true, event: { tool_name: "x" } };
		await boot({ entry: "", css: [] });
		await new Promise((r) => setTimeout(r, 0));
		expect(panel.open).toHaveBeenCalledTimes(1);
	});

	it("opens once for two quick open requests", async () => {
		const bridge = await bootAndGetBridge();
		bridge.emit("open");
		bridge.emit("open");
		await new Promise((r) => setTimeout(r, 0));
		expect(panel.open).toHaveBeenCalledTimes(1);
	});

	it("stops the tooltip cycle and hides a showing tooltip when the panel opens", async () => {
		const bridge = await bootAndGetBridge();
		const root = document.getElementById("fac-widget-launcher").shadowRoot;
		root.querySelector(".faco-tooltip").classList.add("faco-show");
		bridge.emit("open");
		await new Promise((r) => setTimeout(r, 0));
		expect(stopTooltips).toHaveBeenCalled();
	});

	it("starts a fresh tooltip cycle when the panel closes", async () => {
		const bridge = await bootAndGetBridge();
		bridge.emit("open");
		await new Promise((r) => setTimeout(r, 0));
		expect(startTooltips).toHaveBeenCalledTimes(1);
		bridge.emit("close");
		await new Promise((r) => setTimeout(r, 0));
		expect(startTooltips).toHaveBeenCalledTimes(2);
	});

	it("writes the diagnostics switch once, from access alone, even when the widget is hidden", async () => {
		access = { show_widget: false, enable_browser_diagnostics: false };
		await boot({ entry: "", css: [] });
		expect(window.FACODiagnostics.setEnabled).toHaveBeenCalledTimes(1);
		expect(window.FACODiagnostics.setEnabled).toHaveBeenCalledWith(false, true);
	});

	it("writes the diagnostics switch once, unpersisted, when the access check fails", async () => {
		access = new Error("rpc down");
		await boot({ entry: "", css: [] });
		expect(window.FACODiagnostics.setEnabled).toHaveBeenCalledTimes(1);
		expect(window.FACODiagnostics.setEnabled).toHaveBeenCalledWith(true, false);
	});

	it("denies a browser-tool confirmation when the panel fails to load, without an unhandled rejection", async () => {
		const unhandled = vi.fn();
		process.on("unhandledRejection", unhandled);
		ensurePanel.mockRejectedValue(new Error("chunk failed"));
		await boot({ entry: "", css: [] });
		const { confirm } = startBrowserTools.mock.calls[0][0];
		await expect(confirm({ tool: "take_screenshot" })).resolves.toBe("deny");
		await new Promise((r) => setTimeout(r, 0));
		process.off("unhandledRejection", unhandled);
		expect(unhandled).not.toHaveBeenCalled();
	});

	it("swallows a panel load failure on launcher click", async () => {
		ensurePanel.mockRejectedValue(new Error("chunk failed"));
		const unhandled = vi.fn();
		process.on("unhandledRejection", unhandled);
		await boot({ entry: "", css: [] });
		document.getElementById("fac-widget-launcher").shadowRoot.querySelector(".faco-toggle-btn").click();
		await new Promise((r) => setTimeout(r, 0));
		process.off("unhandledRejection", unhandled);
		expect(unhandled).not.toHaveBeenCalled();
	});
});
