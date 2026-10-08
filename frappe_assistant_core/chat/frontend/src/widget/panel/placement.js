const WIDTH = 400;
const HEIGHT = 650;
const SPACING = 16;
const TIGHT = 10;
const MARGIN = 20;
export const COMPACT_BREAKPOINT = 1024;
// At phone width panel.css takes the whole screen; no inline placement may override it.
export const FULLSCREEN_BREAKPOINT = 480;

/**
 * Where the panel sits relative to the launcher button. Same rules as the old
 * widget's position_chat_window: above the button when it fits, else below,
 * else pinned to the top; aligned to the button's edge, else centred. Under
 * 1024px (phone/tablet Desk) it is a bottom sheet above the launcher instead, and
 * at phone width panel.css makes it full screen.
 */
export function computePlacement({ btnRect, width, height }) {
	if (width <= FULLSCREEN_BREAKPOINT) return {};
	if (width < COMPACT_BREAKPOINT) {
		return {
			left: "8px",
			right: "8px",
			top: "auto",
			bottom: "76px",
			width: "auto",
			height: "min(72dvh, calc(100svh - 92px))",
			maxHeight: "min(72dvh, calc(100svh - 92px))",
		};
	}
	if (!btnRect || btnRect.width === 0 || btnRect.height === 0) {
		return {
			left: `${Math.max(MARGIN, (width - WIDTH) / 2)}px`,
			right: "auto",
			top: `${Math.max(MARGIN, (height - HEIGHT) / 2)}px`,
			bottom: "auto",
		};
	}

	const css = {};
	if (btnRect.top >= HEIGHT + SPACING) {
		css.bottom = `${height - btnRect.top + TIGHT}px`;
		css.top = "auto";
	} else if (height - btnRect.bottom >= HEIGHT + SPACING) {
		css.top = `${btnRect.bottom + SPACING}px`;
		css.bottom = "auto";
	} else {
		// Not enough room either way: stay clear of the button; max-height trims the panel.
		css.bottom = `${height - btnRect.top + TIGHT}px`;
		css.top = "auto";
	}

	if (width - btnRect.right >= WIDTH) {
		css.left = `${btnRect.left}px`;
		css.right = "auto";
	} else if (btnRect.left >= WIDTH) {
		css.right = `${width - btnRect.right}px`;
		css.left = "auto";
	} else {
		css.left = `${Math.max(MARGIN, (width - WIDTH) / 2)}px`;
		css.right = "auto";
	}
	return css;
}

const RESET = { left: "", right: "", top: "", bottom: "", width: "", height: "", maxHeight: "" };

/** Position the panel host next to the launcher (the launcher keeps its own saved drag position). */
const hasSize = (r) => !!r && r.width > 0 && r.height > 0;

/**
 * `anchorRect` is the launcher button's rect captured before the open state hid it: a hidden
 * button measures 0x0, which would centre the panel instead of anchoring it. Returns the rect used.
 */
export function placePanel(host, anchorRect = null) {
	const launcher = document.getElementById("fac-widget-launcher");
	const widget = launcher && launcher.shadowRoot && launcher.shadowRoot.querySelector(".faco-toggle-btn");
	const measured = widget ? widget.getBoundingClientRect() : null;
	const btnRect = hasSize(measured) ? measured : anchorRect;
	const css = computePlacement({ btnRect, width: window.innerWidth, height: window.innerHeight });
	Object.assign(host.style, RESET, css);
	return hasSize(btnRect) ? btnRect : null;
}
