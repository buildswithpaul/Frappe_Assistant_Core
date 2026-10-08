import { bridge } from "../bridge.js";

const MESSAGES = [
	{ icon: "👋", text: "Hey! Need help with anything?" },
	{ icon: "💬", text: "Click me to start chatting!" },
	{ icon: "🔍", text: "Looking for something specific?" },
];
const FIRST_DELAY_MS = 3000;
const ROTATE_MS = 8000;
const VISIBLE_MS = 5000;
const GAP = 15;

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

/** One bounded cycle per launch: nudge through each message once, then fall silent. */
export function startTooltips(view, isUserActive) {
	const icon = view.tooltip.querySelector(".faco-tooltip-icon");
	const text = view.tooltip.querySelector(".faco-tooltip-text");
	let index = 0;
	let shown = 0;
	let firstTimer = null;
	let hideTimer = null;
	let interval = null;

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
		const message = MESSAGES[index];
		icon.textContent = message.icon;
		text.textContent = window.__ ? window.__(message.text) : message.text;
		positionTooltip(view.tooltip, view.button);
		view.tooltip.classList.add("faco-show");
		hideTimer = setTimeout(() => view.tooltip.classList.remove("faco-show"), VISIBLE_MS);
		index = (index + 1) % MESSAGES.length;
		shown += 1;
		if (shown >= MESSAGES.length) {
			clearInterval(interval);
			interval = null;
		}
	};

	firstTimer = setTimeout(show, FIRST_DELAY_MS);
	interval = setInterval(show, ROTATE_MS);
	return stop;
}
