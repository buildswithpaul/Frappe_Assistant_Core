import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";

// Frappe's Desk scripts, next to this app in a bench: <bench>/apps/frappe/frappe/public/js/frappe.
const FRAPPE_JS = join("apps", "frappe", "frappe", "public", "js", "frappe");

/** The directory of Frappe's Desk scripts in the bench around this checkout, or null outside one. */
export function findFrappeJs(from = import.meta.dirname) {
	for (let dir = resolve(from); ; dir = dirname(dir)) {
		const candidate = join(dir, FRAPPE_JS);
		if (existsSync(join(candidate, "form", "formatters.js"))) return candidate;
		if (dirname(dir) === dir) return null;
	}
}

// Loaded in this order, as Desk's bundle loads them. Their ES imports are of modules loaded here
// or not needed by the formatter, so they are dropped.
const SCRIPTS = [
	"utils/datatype.js",
	"utils/common.js",
	"utils/number_format.js",
	"sys_defaults.js",
	"utils/datetime.js",
	"model/meta.js",
	"form/formatters.js",
];

function provide(namespace) {
	let target = globalThis;
	for (const part of namespace.split(".")) target = target[part] = target[part] || {};
	return target;
}

/**
 * Desk's own frappe.format, run from Frappe's source: (settings, value, df, options, doc) => html.
 *
 * Only Desk's boot is stood in for: frappe.boot.sysdefaults are the settings' defaults, and the
 * ":Currency" docs Desk boots with are the settings' currencies. Everything that formats is
 * Frappe's code. Sets globals on the test's window, which Vitest gives each spec file afresh.
 */
export function loadDeskFormatter(frappeJs) {
	const require = createRequire(join(frappeJs, "..", "..", "..", "..", "package.json"));
	let current = {};
	Object.assign(globalThis, {
		moment: require("moment"),
		// common.js binds a resize handler as it loads; nothing here resizes.
		$: Object.assign(() => ({ on: () => {} }), { extend: Object.assign, isArray: Array.isArray }),
		__: (text) => text,
		cur_frm: null,
		locals: {},
		frappe: {
			provide,
			ui: {},
			// frappe/public/js/frappe/utils/utils.js, for the Text formatter
			utils: { replace_newlines: (t) => (t ? t.replace(/\n/g, "<br>") : "") },
			dom: { remove_script_and_style: (html) => html },
			model: {
				get_value: (doctype, name, field) =>
					doctype === ":Currency" ? (current.currencies || {})[name]?.[field] : undefined,
			},
		},
	});
	for (const script of SCRIPTS) {
		const source = readFileSync(join(frappeJs, script), "utf-8").replace(/^import .*$/gm, "");
		new Function("window", source)(globalThis);
	}
	return (settings, value, df, options, doc) => {
		current = settings;
		const sysdefaults = Object.fromEntries(Object.entries(settings).filter(([key]) => key !== "currencies"));
		Object.assign(globalThis.frappe, { sys_defaults: sysdefaults, boot: { sysdefaults, user: { defaults: sysdefaults } } });
		// Desk's Float formatter writes its precision into the df it is given.
		return globalThis.frappe.format(value, df && structuredClone(df), options, doc);
	};
}
