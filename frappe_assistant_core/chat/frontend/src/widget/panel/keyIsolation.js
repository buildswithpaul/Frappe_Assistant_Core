const EDITABLE = "input, textarea, select, [contenteditable]:not([contenteditable='false'])";
const KEY_EVENTS = ["keydown", "keypress", "keyup"];

/**
 * Desk's shortcuts skip a keystroke only when `document.activeElement` is a field, but focus inside
 * a shadow root reports the host, so typing `?` or `T` in the composer opened Desk's dialogs.
 * Keys typed into the panel's fields stop at the host. The launcher's own shortcuts listen in the
 * capture phase, so they still fire.
 */
export function isolateTyping(host) {
	const stop = (e) => {
		if (e.composedPath()[0]?.matches?.(EDITABLE)) e.stopPropagation();
	};
	KEY_EVENTS.forEach((type) => host.addEventListener(type, stop));
	return () => KEY_EVENTS.forEach((type) => host.removeEventListener(type, stop));
}
