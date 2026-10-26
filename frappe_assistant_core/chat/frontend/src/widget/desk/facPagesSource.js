import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// The app package root, which render_include resolves "frappe_assistant_core/<path>" against.
const APP_ROOT = resolve(import.meta.dirname, "../../../../..");
const INCLUDE = /\{% include "frappe_assistant_core\/([^"]+)" %\}/g;

/** fac_pages.js as Desk serves it: each include expanded in place, as Frappe's render_include does. */
export function facPagesSource() {
	const source = readFileSync(resolve(APP_ROOT, "assistant_core/page/fac_pages/fac_pages.js"), "utf-8");
	return source.replace(INCLUDE, (_, path) => readFileSync(resolve(APP_ROOT, path), "utf-8"));
}
