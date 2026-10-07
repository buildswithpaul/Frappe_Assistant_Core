import { logger } from "@/utils/logger";
import { bridge } from "./bridge.js";
import { createLauncherView } from "./launcher/view.js";
import { checkAccess, applyDiagnosticsSwitch } from "./launcher/access.js";
import { mirrorDeskTheme } from "./launcher/theme.js";
import { installFontFaces } from "./launcher/fonts.js";
import { restorePosition, enableDrag, consumeDrag } from "./launcher/position.js";
import { setupAutofade, isUserActive } from "./launcher/autofade.js";
import { startTooltips } from "./launcher/tooltips.js";
import { bindShortcut, bindMicShortcut } from "./launcher/shortcut.js";
import { raiseAttention, clearAttention } from "./launcher/attention.js";
import { hasPendingInterrupt } from "./launcher/pending.js";
import { refreshSpotlightDot } from "./launcher/spotlightDot.js";
import { ensurePanel, destroyPanel } from "./launcher/panelLoader.js";
import { startStreamWatch } from "./launcher/streamWatch.js";
import { resolveWidgetSession, startClaimResponder } from "./desk/session.js";
import { startBrowserTools, stopBrowserTools } from "./desk/browserTools.js";

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
		// The server's except-branch answers 200 without `privacy`; treating that as loaded
		// would read as "extraction on", so only a response carrying `privacy` counts.
		const message = r.message;
		widgetSettings = message && typeof message.privacy === "object" && message.privacy ? message : null;
	} catch (err) {
		logger.error("[FAC widget] settings", err);
	}
}

let lastConfig = null;
let teardownCurrent = () => {};

/** Undo boot(): FAC Admin's chat toggle removes the widget without a page reload. */
function teardown() {
	teardownCurrent();
	teardownCurrent = () => {};
	bridge.state.open = false;
	bridge.state.attention = false;
	window.__facWidgetBooted = false;
}

async function remount() {
	teardown();
	if (lastConfig) await boot(lastConfig);
}

export async function boot(config) {
	if (window.__facWidgetBooted) return;
	window.__facWidgetBooted = true;
	lastConfig = config;
	window.facoWidgetTeardown = teardown;
	window.facoWidgetRemount = remount;
	const cleanups = [];
	let hidden = false;
	let panelMounted = false;
	teardownCurrent = () => {
		hidden = true;
		cleanups.splice(0).reverse().forEach((fn) => {
			try {
				fn();
			} catch (err) {
				logger.error("[FAC widget] teardown", err);
			}
		});
	};

	const [access, session] = await Promise.all([checkAccess(), resolveWidgetSession()]);
	applyDiagnosticsSwitch(access);
	bridge.state.access = access;
	bridge.state.sessionId = session.session_id;
	bridge.state.restored = session.restored;
	cleanups.push(startClaimResponder(() => bridge.state.sessionId));
	cleanups.push(bridge.on("session", (sid) => (bridge.state.sessionId = sid)));

	if (!access.show_widget) return;
	const prefs = access.preferences || {};
	if (prefs.hide_widget) return;

	installFontFaces();
	const view = createLauncherView(document);
	cleanups.push(() => view.destroy());
	cleanups.push(() => clearAttention(view));
	cleanups.push(mirrorDeskTheme(view.host));
	restorePosition(view.widgetEl);
	enableDrag(view.widgetEl, view.button);
	setupAutofade(view.widgetEl);

	let stopTooltips = startTooltips(view, isUserActive);
	cleanups.push(() => stopTooltips());
	const mountPanel = async () => {
		const panel = await ensurePanel(config);
		panelMounted = true;
		return panel;
	};

	// One in-flight open: raiseAttention, the pending-interrupt path and a browser-tool
	// confirm can all ask at once, and panel.open() must run a single time.
	let opening = null;
	const open = () => {
		if (bridge.state.open) return Promise.resolve();
		if (!opening) {
			opening = (async () => {
				const panel = await mountPanel();
				// Measured before setOpen hides the button (display:none reads 0x0).
				const anchorRect = view.button.getBoundingClientRect();
				bridge.state.open = true;
				view.setOpen(true);
				stopTooltips();
				panel.open({ anchorRect });
			})().finally(() => (opening = null));
		}
		return opening;
	};
	const close = async () => {
		const panel = await mountPanel();
		bridge.state.open = false;
		view.setOpen(false);
		panel.close();
		// Closing starts a fresh tooltip cycle.
		stopTooltips();
		stopTooltips = startTooltips(view, isUserActive);
	};
	// Desk must never see a rejection from a panel that failed to load.
	const guarded = (fn) => () =>
		fn().catch((err) => logger.error("[FAC widget] panel", err));
	const toggle = guarded(() => (bridge.state.open ? close() : open()));
	view.button.addEventListener("click", () => {
		if (consumeDrag()) return;
		toggle();
	});
	cleanups.push(bridge.on("open", guarded(open)));
	cleanups.push(bridge.on("close", guarded(close)));
	cleanups.push(bridge.on("mood", (m) => view.setMood(m)));
	cleanups.push(bridge.on("attention", (info) => raiseAttention(view, info)));
	cleanups.push(bridge.on("attention-clear", () => clearAttention(view)));
	const unbindToggle = prefs.keyboard_shortcut ? bindShortcut(prefs.keyboard_shortcut, toggle) : () => {};
	// Bound here, not in the lazy panel, so it works on a fresh page before the panel has ever opened.
	// The panel consumes micRequested when it mounts, or the "mic" event if it is already up.
	const unbindMic = bindMicShortcut(() => {
		bridge.state.micRequested = true;
		bridge.emit("open");
		bridge.emit("mic");
	});
	cleanups.push(unbindToggle, unbindMic);
	// "Hide assistant" must also stop the shortcuts, and any later browser-tool prompt, reopening what the user hid.
	cleanups.push(
		bridge.on("hide", () => {
			hidden = true;
			unbindToggle();
			unbindMic();
			view.destroy();
			destroyPanel();
		})
	);
	cleanups.push(() => destroyPanel());

	const syncVisibility = () => {
		const route = window.frappe && window.frappe.get_route ? window.frappe.get_route() : [];
		view.host.style.display = HIDDEN_ROUTES.has(route && route[0]) ? "none" : "";
	};
	syncVisibility();
	if (window.frappe && window.frappe.router) {
		window.frappe.router.on("change", syncVisibility);
		cleanups.push(() => window.frappe.router.off && window.frappe.router.off("change", syncVisibility));
	}

	await loadWidgetSettings();

	// Calls arrive with the panel closed: a navigate_to lands on a fresh page.
	if (hidden) return;
	startBrowserTools({
		getSessionId: () => bridge.state.sessionId,
		getWidgetSettings: () => widgetSettings || FAIL_CLOSED_SETTINGS,
		confirm: (request) =>
			new Promise((resolve) => {
				if (hidden) return resolve("deny");
				open()
					.then(() => bridge.emit("confirm", { request, resolve }))
					.catch((err) => {
						logger.error("[FAC widget] confirm", err);
						resolve("deny");
					});
			}),
	});

	cleanups.push(stopBrowserTools);
	refreshSpotlightDot(view, access);

	if (access.can_use) {
		const stopWatch = startStreamWatch({
			getSessionId: () => bridge.state.sessionId,
			isMounted: () => panelMounted,
			ensurePanel: () => {
				// The turn is already under way: let the panel load its history before it takes over.
				bridge.state.restored = true;
				return mountPanel();
			},
			onApproval: (info) => raiseAttention(view, info),
		});
		cleanups.push(bridge.on("session", () => stopWatch.resubscribe()));
		cleanups.push(stopWatch);
	}

	// A pause that survived a reload must not wait for a click; raiseAttention opens the panel.
	try {
		if (access.can_use && (await hasPendingInterrupt(bridge.state.sessionId))) {
			raiseAttention(view, {});
		}
	} catch (err) {
		logger.error("[FAC widget] pending", err);
	}
}
