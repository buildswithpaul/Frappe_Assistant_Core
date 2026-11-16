/**
 * Frappe's messages carry markup (<strong>, <br>); where one is shown or passed on as text, keep only
 * the text. DOMParser builds an inert document (no script runs, nothing loads) and textContent decodes
 * entities without ever turning them back into markup. A regex that strips tags is not enough: on
 * "<scr<b>ipt>" it removes "<b>" and leaves "<script>" behind (code scanning alert #13).
 */
export function htmlText(text) {
	const doc = new DOMParser().parseFromString(String(text ?? "").replace(/<br\s*\/?>/gi, " "), "text/html");
	return (doc.body.textContent || "").replace(/ /g, " ").replace(/[ \t]+/g, " ");
}
