export function parseShortcut(s) {
	const parts = String(s || "")
		.split("+")
		.map((p) => p.trim().toLowerCase());
	const key = parts.pop() || "";
	return { key, ctrl: parts.includes("ctrl"), shift: parts.includes("shift"), alt: parts.includes("alt") };
}

/**
 * Ctrl+Shift+Space: open the panel and start voice input. Typing in some other input on the Desk
 * page is left alone; the panel's own composer lives in a shadow root, so its events retarget to the host.
 */
export function bindMicShortcut(onFire) {
	const handler = (e) => {
		if (!(e.ctrlKey && e.shiftKey && (e.key === " " || e.code === "Space"))) return;
		const tag = e.target && e.target.tagName;
		if (tag === "INPUT" || tag === "TEXTAREA") return;
		e.preventDefault();
		onFire();
	};
	document.addEventListener("keydown", handler);
	return () => document.removeEventListener("keydown", handler);
}

/** A modifier the shortcut does not name must NOT be held, so Ctrl+K never fires on Ctrl+Shift+K. */
export function bindShortcut(s, onFire) {
	const want = parseShortcut(s);
	if (!want.key) return () => {};
	const handler = (e) => {
		if (e.key.toLowerCase() !== want.key) return;
		if (want.ctrl !== (e.ctrlKey || e.metaKey) || want.shift !== e.shiftKey || want.alt !== e.altKey) return;
		e.preventDefault();
		onFire();
	};
	document.addEventListener("keydown", handler);
	return () => document.removeEventListener("keydown", handler);
}
