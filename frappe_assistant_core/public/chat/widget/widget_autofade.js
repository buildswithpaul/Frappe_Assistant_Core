// Frappe Assistant Copilot - Powered by FAC Cloud
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

/**
 * FACO Widget Autofade
 *
 * Fades the closed launcher to ~15% opacity (and makes it click-through)
 * while the user is actively interacting with the rest of the page
 * (typing in a Frappe input, or scrolling the Desk main pane). Restores
 * after ~700 ms of idle.
 *
 * Suppressed when:
 *   - The chat window is open (.faco-open class)
 *   - An approval is pending (.faco-awaiting-approval class)
 *   - The user is dragging the widget (.faco-dragging class)
 *   - The first 400 ms after init (avoids flash on page load)
 *   - The interaction originates from inside the widget itself
 */
window.FACOWidgetAutofade = {
	IDLE_MS: 700,
	BOOT_GRACE_MS: 400,
	FADE_CLASS: "faco-fade",

	setup(widget) {
		const $widgetEl = widget.$widget;
		if (!$widgetEl || !$widgetEl[0]) return;

		const el = $widgetEl[0];
		const bootedAt = Date.now();
		let idleTimer = null;
		let isFaded = false;

		const shouldSuppress = (eventTarget) => {
			if (Date.now() - bootedAt < this.BOOT_GRACE_MS) return true;
			if (el.classList.contains("faco-open")) return true;
			if (el.classList.contains("faco-dragging")) return true;
			// The assistant is blocked on a decision — never dim the launcher.
			if (el.classList.contains("faco-awaiting-approval")) return true;
			// Phone/tablet Desk is almost always scrolling; 15% opacity plus
			// pointer-events:none made the launcher look missing and untappable.
			if (window.innerWidth < 1024) return true;
			// Interactions inside the widget itself don't fade it.
			if (eventTarget && el.contains(eventTarget)) return true;
			return false;
		};

		const applyFade = () => {
			if (window.innerWidth < 1024) return;
			if (!isFaded) {
				el.classList.add(this.FADE_CLASS);
				isFaded = true;
			}
		};

		const scheduleRestore = () => {
			if (idleTimer) clearTimeout(idleTimer);
			idleTimer = setTimeout(() => {
				el.classList.remove(this.FADE_CLASS);
				isFaded = false;
				idleTimer = null;
				// Page is idle again; tooltips may resume on the next tick.
				widget._userActive = false;
			}, this.IDLE_MS);
		};

		const onActivity = (e) => {
			if (shouldSuppress(e && e.target)) return;
			// Shared signal: the tooltip reads this to stay hidden while the
			// user is typing/scrolling, and only nudges during genuine idle.
			widget._userActive = true;
			applyFade();
			scheduleRestore();
		};

		// Typing anywhere on the page: keydown bubbles from any focused input.
		document.addEventListener("keydown", onActivity, true);

		// Scrolling: passive for perf.
		window.addEventListener("scroll", onActivity, { passive: true, capture: true });

		// Mouse wheel without scroll context (some Desk panes use overflow:hidden).
		window.addEventListener("wheel", onActivity, { passive: true, capture: true });

		window.addEventListener("resize", () => {
			if (window.innerWidth < 1024) {
				el.classList.remove(this.FADE_CLASS);
				isFaded = false;
			}
		});
	},
};
