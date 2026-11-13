/**
 * Present mode for a FAC Page: the page full screen, one `mk-section` at a time, with its edit
 * controls hidden. makePresenter switches the sections in the document the page lives in (a shared
 * page's shadow root, or a personal page's own frame); mountPresentControls draws the controls,
 * asks for full screen and maps the keys, around any deck that can start, show and stop, local or
 * across the personal page's frame. Bundled for Desk (pageFacBundle.js) and the frame runtime.
 */
import { deskTheme, followDeskTheme } from "@/utils/deskTheme";
import { __ } from "@/utils/i18n";

const PRESENTING = "fac-presenting";
const OFF = "fac-present-off";
const CONTAINER = "fac-present-container";
// The container is outside the page's shadow root, where the kit's styles do not reach, so its
// presenting look is set inline: it covers the screen (full screen or not, so the bar is always in
// view) and scrolls inside, and without a background full screen shows a black backdrop. The
// background is the kit's page background in Desk's theme.
const CONTAINER_STYLE = {
	position: "fixed",
	inset: "0",
	zIndex: "2147482999",
	display: "flex",
	flexDirection: "column",
	overflow: "auto",
	padding: "24px",
	boxSizing: "border-box",
};

// The kit's --mk-bg in each theme (mockup_kit.css).
const PAGE_BACKGROUND = { light: "#ffffff", dark: "#171717" };

const KEYS = {
	ArrowRight: "next",
	ArrowDown: "next",
	PageDown: "next",
	" ": "next",
	ArrowLeft: "prev",
	ArrowUp: "prev",
	PageUp: "prev",
	Home: "first",
	End: "last",
	Escape: "exit",
};

/** What a key does while presenting, or null; typing in a field is left alone. */
export function presentKey(event) {
	if (event.ctrlKey || event.metaKey || event.altKey) return null;
	// A key pressed in a shared page's shadow root reaches the document retargeted to its host, so
	// the field it was typed in is the first entry of its composed path.
	const target = event.composedPath?.()[0] || event.target;
	if (target?.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target?.tagName || "")) return null;
	return KEYS[event.key] || null;
}

function titleOf(section, n) {
	const title = section.dataset.title || section.querySelector("h1, h2, h3, h4")?.textContent || "";
	return title.trim() || __("Section {0}", [n]);
}

/** Switches the sections of the page held by `root` (an element, a shadow root or a document). */
export function makePresenter(root) {
	const pageElement = () =>
		root.querySelector(".fac-page-root") || root.documentElement || root.host || root.firstElementChild || root;
	const sections = () => [...root.querySelectorAll(".mk-section")];
	let index = 0;

	function state() {
		const all = sections();
		return {
			index,
			count: Math.max(all.length, 1),
			titles: all.length ? all.map((section, i) => titleOf(section, i + 1)) : [root.title || ""],
		};
	}

	function show(next) {
		const all = sections();
		index = Math.min(Math.max(Number(next) || 0, 0), Math.max(all.length - 1, 0));
		all.forEach((section, i) => section.classList.toggle(OFF, i !== index));
		return state();
	}

	return {
		start() {
			pageElement().classList.add(PRESENTING);
			return show(0);
		},
		show,
		stop() {
			pageElement().classList.remove(PRESENTING);
			sections().forEach((section) => section.classList.remove(OFF));
			index = 0;
		},
	};
}

function control(tag, className, label, text) {
	const node = document.createElement(tag);
	node.className = className;
	if (tag === "button") node.type = "button";
	if (label) node.setAttribute("aria-label", label);
	if (text !== undefined) node.textContent = text;
	node.style.cssText =
		"min-width:44px;min-height:44px;border:0;border-radius:999px;background:transparent;color:#fff;font:inherit;cursor:pointer;";
	return node;
}

/**
 * Presents `deck` in `container`: controls at its foot, full screen when allowed, and the keys.
 * Resolves `{key(action), stop()}`; leaving full screen, Exit or Escape stops it. `theme` is the
 * page's theme, "dark" or "light", or a function giving it; it is read again when Desk's changes.
 */
export async function mountPresentControls({ container, deck, onExit, fullscreen = true, theme = deskTheme }) {
	const doc = container.ownerDocument;
	let state = await deck.start();
	let stopped = false;
	let enteredFullscreen = false;
	const savedStyle = container.style.cssText;
	const paint = () => {
		const current = typeof theme === "function" ? theme() : theme;
		container.style.background = PAGE_BACKGROUND[current === "dark" ? "dark" : "light"];
	};
	let stopTheme = () => {};

	const bar = document.createElement("div");
	bar.className = "fac-present-bar";
	bar.setAttribute("role", "toolbar");
	bar.setAttribute("aria-label", __("Present"));
	// Last in the scrolling container: at its foot when the section is short, held there by sticky
	// when the section is taller than the screen.
	bar.style.cssText =
		"position:sticky;bottom:0;margin:auto auto 0;flex:none;z-index:2147483000;display:flex;align-items:center;gap:4px;" +
		"width:max-content;max-width:100%;padding:4px 8px;border-radius:999px;background:rgba(17,17,17,0.82);color:#fff;font:14px/1.4 sans-serif;";
	const prev = control("button", "fac-present-prev", __("Previous section"), "◀");
	const where = control("span", "fac-present-where");
	where.style.cssText = "padding:0 12px;white-space:nowrap;max-width:60vw;overflow:hidden;text-overflow:ellipsis;";
	where.setAttribute("aria-live", "polite");
	const next = control("button", "fac-present-next", __("Next section"), "▶");
	const exit = control("button", "fac-present-exit", __("Exit"), __("Exit"));
	exit.style.padding = "0 14px";
	bar.append(prev, where, next, exit);

	function draw() {
		const title = state.titles?.[state.index] || "";
		where.textContent = `${state.index + 1} / ${state.count}${title ? ` · ${title}` : ""}`;
		prev.disabled = state.index <= 0;
		next.disabled = state.index >= state.count - 1;
	}

	async function key(action) {
		if (stopped) return;
		if (action === "exit") return stop();
		const target = { next: state.index + 1, prev: state.index - 1, first: 0, last: state.count - 1 }[action];
		if (target === undefined) return;
		state = await deck.show(target);
		draw();
	}

	const onKey = (event) => {
		const action = presentKey(event);
		if (!action) return;
		event.preventDefault();
		key(action);
	};
	const onFullscreen = () => {
		if (enteredFullscreen && !doc.fullscreenElement) stop();
	};

	async function stop() {
		if (stopped) return;
		stopped = true;
		doc.removeEventListener("keydown", onKey);
		doc.removeEventListener("fullscreenchange", onFullscreen);
		stopTheme();
		bar.remove();
		container.classList.remove(CONTAINER);
		container.style.cssText = savedStyle;
		if (doc.fullscreenElement === container) await doc.exitFullscreen?.().catch(() => {});
		await deck.stop();
		onExit?.();
	}

	prev.addEventListener("click", () => key("prev"));
	next.addEventListener("click", () => key("next"));
	exit.addEventListener("click", () => key("exit"));
	doc.addEventListener("keydown", onKey);
	doc.addEventListener("fullscreenchange", onFullscreen);
	container.classList.add(CONTAINER);
	Object.assign(container.style, CONTAINER_STYLE);
	paint();
	// After a Vue watcher or Desk's own observer has passed the change on to the page.
	stopTheme = followDeskTheme(() => setTimeout(paint));
	container.append(bar);
	draw();

	if (fullscreen && container.requestFullscreen) {
		try {
			await container.requestFullscreen();
			enteredFullscreen = true;
		} catch {
			// Refused or unsupported: present inside the page's own area.
		}
	}
	return {
		key,
		stop,
		get active() {
			return !stopped;
		},
	};
}

/**
 * The deck for a personal page, whose frame presents its own sections. A start the frame answered
 * too late still switched it into present mode, so a failed start tells it to stop.
 */
export function remoteDeck(frame) {
	return {
		start: () =>
			frame.present("start").catch((error) => {
				frame.present("stop").catch(() => {});
				throw error;
			}),
		show: (index) => frame.present("show", index),
		stop: () => frame.present("stop").catch(() => {}),
	};
}
