import { bridge } from "../bridge.js";

const FLASH_MS = 1200;
let flashTimer = null;
let originalTitle = "";

// Alternates the tab title so a backgrounded tab still shows the ask.
function startTitleFlash() {
	if (flashTimer) return;
	originalTitle = document.title;
	let showing = false;
	flashTimer = setInterval(() => {
		showing = !showing;
		document.title = showing ? window.__("● Approval needed") : originalTitle;
	}, FLASH_MS);
}

function stopTitleFlash() {
	if (!flashTimer) return;
	clearInterval(flashTimer);
	flashTimer = null;
	if (originalTitle) document.title = originalTitle;
}

/**
 * Make a pending approval impossible to miss: a card in a closed panel is hidden DOM, so
 * pop the panel open, badge the launcher (which also suppresses autofade), toast, and
 * flash the tab title. Safe to call repeatedly: only the first call toasts and flashes.
 */
export function raiseAttention(view, info) {
	view.setAttention(true);
	const alreadyRaised = bridge.state.attention;
	bridge.state.attention = true;
	bridge.emit("open");
	// The boot-time check and the panel's own watcher both raise the same pause; one toast is enough.
	if (alreadyRaised) return;

	const toolName = info && info.tool_name;
	if (window.frappe && window.frappe.show_alert) {
		window.frappe.show_alert(
			{
				message: toolName
					? window.__("Approval needed: {0}", [toolName])
					: window.__("The assistant needs your approval"),
				indicator: "orange",
			},
			10,
		);
	}
	startTitleFlash();
}

/** Drop every attention signal. Safe to call when none is active. */
export function clearAttention(view) {
	view.setAttention(false);
	bridge.state.attention = false;
	stopTitleFlash();
}
