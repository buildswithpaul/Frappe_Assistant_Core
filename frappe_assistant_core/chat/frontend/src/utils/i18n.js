/**
 * Translation marker for the FAC Chat SPA.
 *
 * Same contract as the Desk widget's `t` (widget/panel/i18n.js): Frappe's
 * `window.__` when the page has loaded it, otherwise the English source with
 * {0}-style arguments filled in. The SPA shell does not load a translation
 * dictionary today, so this mostly marks strings; the call sites are ready
 * when one is added.
 */
const fill = (text, args) =>
	args ? String(text).replace(/\{(\d+)\}/g, (match, i) => args[i] ?? match) : text;

export function __(text, args) {
	if (typeof window !== "undefined" && typeof window.__ === "function") {
		return window.__(text, args);
	}
	return fill(text, args);
}
