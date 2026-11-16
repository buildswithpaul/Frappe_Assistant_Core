import { bridge } from "../bridge.js";
import { detectContext } from "../desk/pageContext.js";
import { getHost } from "../host/index.js";

const MESSAGES = [
	{ icon: "👋", text: "Hey! Need help with anything?" },
	{ icon: "💬", text: "Click me to start chatting!" },
	{ icon: "🔍", text: "Looking for something specific?" },
];
const FIRST_DELAY_MS = 3000;
const ROTATE_MS = 8000;
const VISIBLE_MS = 5000;
const GAP = 15;
export const NEW_USER_DAYS = 7;
const DAY_MS = 86_400_000;
const FIRST_SEEN_KEY = (user) => `fac_launcher_first_seen:${user}`;

const translate = (text, args) =>
	window.__ ? window.__(text, args) : text.replace(/\{(\d+)\}/g, (_, i) => (args ? args[i] : ""));

/**
 * True during a user's first 7 days with the launcher on this browser. The first call stamps
 * the day; storage that cannot be read counts as not new, so the old messages show.
 */
export function isNewToFac(user, now = Date.now()) {
	if (!user) return false;
	try {
		let first = Number(window.localStorage.getItem(FIRST_SEEN_KEY(user)));
		if (!first) {
			first = now;
			window.localStorage.setItem(FIRST_SEEN_KEY(user), String(now));
		}
		return now - first < NEW_USER_DAYS * DAY_MS;
	} catch {
		return false;
	}
}

/** A message about the page the user is on (a saved record, a list or a report); null anywhere else. */
export function pageMessage(context) {
	if (!context) return null;
	if (context.type === "Form" && context.name && !context.is_new) {
		return { icon: "💬", text: translate("Ask me anything about {0}", [context.name]) };
	}
	if (context.type === "List" && context.doctype) {
		return { icon: "🔍", text: translate("Ask me about your {0} list", [translate(context.doctype)]) };
	}
	if (context.type === "Report" && context.name) {
		return { icon: "📊", text: translate("Ask me to explain {0}", [translate(context.name)]) };
	}
	return null;
}

function currentPageMessage() {
	try {
		return pageMessage(detectContext());
	} catch {
		return null;
	}
}

function positionTooltip(tooltip, button) {
	const btn = button.getBoundingClientRect();
	const width = tooltip.offsetWidth;
	const top = btn.top + btn.height / 2 - tooltip.offsetHeight / 2 + "px";
	if (btn.left >= width + 20) {
		Object.assign(tooltip.style, {
			right: window.innerWidth - btn.left + GAP + "px",
			left: "auto",
			top,
			bottom: "auto",
		});
		tooltip.setAttribute("data-arrow", "right");
	} else {
		Object.assign(tooltip.style, { left: btn.right + GAP + "px", right: "auto", top, bottom: "auto" });
		tooltip.setAttribute("data-arrow", "left");
	}
}

/**
 * One bounded cycle per launch: nudge through each message once, then fall silent. In a user's
 * first 7 days, on a record, list or report, the cycle is one message about that page instead.
 */
export function startTooltips(view, isUserActive) {
	const icon = view.tooltip.querySelector(".faco-tooltip-icon");
	const text = view.tooltip.querySelector(".faco-tooltip-text");
	let index = 0;
	let shown = 0;
	let firstTimer = null;
	let hideTimer = null;
	let interval = null;
	const newUser = isNewToFac(getHost().user());

	const stop = () => {
		clearTimeout(firstTimer);
		clearTimeout(hideTimer);
		clearInterval(interval);
		interval = null;
		view.tooltip.classList.remove("faco-show");
	};

	const show = () => {
		if (bridge.state.open || shown >= MESSAGES.length) return;
		// Skip, without burning a message, while the user is typing or scrolling.
		if (isUserActive()) return;
		const aboutPage = newUser ? currentPageMessage() : null;
		const message = aboutPage || { ...MESSAGES[index], text: translate(MESSAGES[index].text) };
		icon.textContent = message.icon;
		text.textContent = message.text;
		positionTooltip(view.tooltip, view.button);
		view.tooltip.classList.add("faco-show");
		hideTimer = setTimeout(() => view.tooltip.classList.remove("faco-show"), VISIBLE_MS);
		index = (index + 1) % MESSAGES.length;
		// The page message is the whole cycle: one nudge, then quiet.
		shown = aboutPage ? MESSAGES.length : shown + 1;
		if (shown >= MESSAGES.length) {
			clearInterval(interval);
			interval = null;
		}
	};

	firstTimer = setTimeout(show, FIRST_DELAY_MS);
	interval = setInterval(show, ROTATE_MS);
	return stop;
}
