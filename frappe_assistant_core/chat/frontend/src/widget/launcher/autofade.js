const FADE_CLASS = "faco-fade";
const LAPTOP_WIDTH = 1024;

let userActive = false;

/** Shared signal: tooltips stay quiet while the user is typing or scrolling. */
export const isUserActive = () => userActive;

/**
 * Fades the closed launcher to ~15% opacity (and click-through) while the user types or
 * scrolls the page, and restores it after idleMs. Suppressed while the panel is open, an
 * approval is pending, the launcher is being dragged, during the boot grace, below laptop
 * width, and for interactions that start inside the widget.
 */
export function setupAutofade(el, { bootGraceMs = 400, idleMs = 700 } = {}) {
	const bootedAt = Date.now();
	let idleTimer = null;
	let isFaded = false;

	const shouldSuppress = (event) => {
		if (Date.now() - bootedAt < bootGraceMs) return true;
		if (el.classList.contains("faco-open")) return true;
		if (el.classList.contains("faco-dragging")) return true;
		// The assistant is blocked on a decision: never dim the launcher.
		if (el.classList.contains("faco-awaiting-approval")) return true;
		// Phone/tablet Desk is almost always scrolling; 15% opacity plus
		// pointer-events:none made the launcher look missing and untappable.
		if (window.innerWidth < LAPTOP_WIDTH) return true;
		// The listener sits on window, where a shadow-DOM target is retargeted to the host.
		const path = event && event.composedPath ? event.composedPath() : [];
		if (path.includes(el)) return true;
		return false;
	};

	const scheduleRestore = () => {
		if (idleTimer) clearTimeout(idleTimer);
		idleTimer = setTimeout(() => {
			el.classList.remove(FADE_CLASS);
			isFaded = false;
			idleTimer = null;
			userActive = false;
		}, idleMs);
	};

	const onActivity = (e) => {
		if (shouldSuppress(e)) return;
		userActive = true;
		if (!isFaded) {
			el.classList.add(FADE_CLASS);
			isFaded = true;
		}
		scheduleRestore();
	};

	document.addEventListener("keydown", onActivity, true);
	window.addEventListener("scroll", onActivity, { passive: true, capture: true });
	window.addEventListener("wheel", onActivity, { passive: true, capture: true });
	window.addEventListener("resize", () => {
		if (window.innerWidth < LAPTOP_WIDTH) {
			el.classList.remove(FADE_CLASS);
			isFaded = false;
		}
	});
}
