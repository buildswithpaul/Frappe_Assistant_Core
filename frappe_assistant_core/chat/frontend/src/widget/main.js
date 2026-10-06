import { logger } from "@/utils/logger";
import { bridge } from "./bridge.js";
import { createLauncherView } from "./launcher/view.js";
import { checkAccess, applyDiagnosticsSwitch } from "./launcher/access.js";
import { mirrorDeskTheme } from "./launcher/theme.js";
import { installFontFaces } from "./launcher/fonts.js";
import { restorePosition, enableDrag, consumeDrag } from "./launcher/position.js";
import { setupAutofade, isUserActive } from "./launcher/autofade.js";
import { startTooltips } from "./launcher/tooltips.js";
import { bindShortcut } from "./launcher/shortcut.js";
import { raiseAttention, clearAttention } from "./launcher/attention.js";
import { hasPendingInterrupt } from "./launcher/pending.js";
import { refreshSpotlightDot } from "./launcher/spotlightDot.js";
import { ensurePanel } from "./launcher/panelLoader.js";
import { resolveWidgetSession, startClaimResponder } from "./desk/session.js";
import { startBrowserTools } from "./desk/browserTools.js";

const HIDDEN_ROUTES = new Set(["faco-assistant"]);

// The operator's privacy settings. While unloaded (or if the fetch failed) DOM extraction
// stays off: browserTools only treats an explicit `false` as off, so an empty object would
// fail open.
const FAIL_CLOSED_SETTINGS = { privacy: { enable_dom_extraction: false } };
let widgetSettings = null;

async function loadWidgetSettings() {
	try {
		const r = await window.frappe.call({
			method: "frappe_assistant_core.chat.api.settings.widget.get_widget_settings",
			type: "GET",
			args: {},
		});
		widgetSettings = r.message || null;
	} catch (err) {
		logger.error("[FAC widget] settings", err);
	}
}

export async function boot(config) {
	if (window.__facWidgetBooted) return;
	window.__facWidgetBooted = true;

	const [access, session] = await Promise.all([checkAccess(), resolveWidgetSession()]);
	applyDiagnosticsSwitch(access);
	bridge.state.access = access;
	bridge.state.sessionId = session.session_id;
	bridge.state.restored = session.restored;
	startClaimResponder(() => bridge.state.sessionId);
	bridge.on("session", (sid) => (bridge.state.sessionId = sid));

	if (!access.show_widget) return;
	const prefs = access.preferences || {};
	if (prefs.hide_widget) return;

	installFontFaces();
	const view = createLauncherView(document);
	mirrorDeskTheme(view.host);
	restorePosition(view.widgetEl);
	enableDrag(view.widgetEl, view.button);
	setupAutofade(view.widgetEl);
	startTooltips(view, isUserActive);

	const open = async () => {
		const panel = await ensurePanel(config);
		bridge.state.open = true;
		view.setOpen(true);
		panel.open();
	};
	const close = async () => {
		const panel = await ensurePanel(config);
		bridge.state.open = false;
		view.setOpen(false);
		panel.close();
	};
	const toggle = () => (bridge.state.open ? close() : open());
	view.button.addEventListener("click", () => {
		if (consumeDrag()) return;
		toggle();
	});
	bridge.on("open", open);
	bridge.on("close", close);
	bridge.on("mood", (m) => view.setMood(m));
	bridge.on("attention", (info) => raiseAttention(view, info));
	bridge.on("attention-clear", () => clearAttention(view));
	if (prefs.keyboard_shortcut) bindShortcut(prefs.keyboard_shortcut, toggle);

	const syncVisibility = () => {
		const route = window.frappe && window.frappe.get_route ? window.frappe.get_route() : [];
		view.host.style.display = HIDDEN_ROUTES.has(route && route[0]) ? "none" : "";
	};
	syncVisibility();
	if (window.frappe && window.frappe.router) window.frappe.router.on("change", syncVisibility);

	await loadWidgetSettings();

	// Calls arrive with the panel closed: a navigate_to lands on a fresh page.
	startBrowserTools({
		getSessionId: () => bridge.state.sessionId,
		getWidgetSettings: () => widgetSettings || FAIL_CLOSED_SETTINGS,
		confirm: (request) =>
			new Promise((resolve) => {
				open().then(() => bridge.emit("confirm", { request, resolve }));
			}),
	});

	refreshSpotlightDot(view, access);

	// A pause that survived a reload must not wait for a click.
	if (access.can_use && (await hasPendingInterrupt(bridge.state.sessionId))) {
		await ensurePanel(config);
		raiseAttention(view, {});
		open();
	}
}
