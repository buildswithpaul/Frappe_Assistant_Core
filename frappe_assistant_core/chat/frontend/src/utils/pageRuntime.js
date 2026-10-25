/**
 * Runs a FAC Page's script in the chat panel, where Desk's `frappe` global does not exist.
 *
 * The stand-in offers the part of `frappe` a page needs to read and write data, through the
 * same-origin session the SPA already uses. Any other member a script reaches for is reported
 * as unsupported, so the panel can send the user to Desk instead of drawing a broken page.
 */
import { __ } from "@/utils/i18n";

// A GET query string carries text only; Frappe parses JSON-encoded args back on the server.
const toQuery = (args = {}) =>
	Object.fromEntries(
		Object.entries(args).map(([key, value]) => [
			key,
			value !== null && typeof value === "object" ? JSON.stringify(value) : value,
		]),
	);

// What each stand-in has reported, so runPageScript can say what a script reached for while it ran.
const UNSUPPORTED = new WeakMap();

const pad = (n) => String(n).padStart(2, "0");

function today() {
	const now = new Date();
	return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function strToUser(value) {
	if (!value) return "";
	const date = new Date(String(value).length === 10 ? `${value}T00:00:00` : value);
	return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString();
}

const ISO_CURRENCY = /^[A-Z]{3}$/;

function format(value, df = {}) {
	if (value === null || value === undefined || value === "") return "";
	const number = Number(value);
	switch (df.fieldtype) {
		case "Currency":
			return ISO_CURRENCY.test(df.options || "")
				? new Intl.NumberFormat("en-US", { style: "currency", currency: df.options }).format(number)
				: new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(number);
		case "Float":
			return new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(number);
		case "Int":
			return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Math.round(number));
		case "Date":
			return strToUser(value);
		default:
			return String(value);
	}
}

// Reading a member the target lacks reports it by path and gives undefined, as Desk would not.
function guard(target, path, report) {
	return new Proxy(target, {
		get(obj, key, receiver) {
			if (typeof key === "symbol" || key in obj) return Reflect.get(obj, key, receiver);
			report(path ? `${path}.${key}` : key);
			return undefined;
		},
	});
}

/**
 * The `frappe` a page script sees in the panel.
 *
 * @param {{baseCall: Function, getCall: Function, user: string}} api the SPA transport and session user
 * @param {{onUnsupported?: (name: string) => void, onError?: (error: Error) => void}} options
 *   `onUnsupported` gets each unsupported member's path; `onError` gets a failed call the script
 *   passed no error callback for, which would otherwise leave part of the page silently empty.
 */
export function makeFrappeStandIn(api, { onUnsupported, onError } = {}) {
	const unsupported = [];
	const report = (name) => {
		unsupported.push(name);
		onUnsupported?.(name);
	};

	function call(opts, args, callback) {
		const o = typeof opts === "string" ? { method: opts, args, callback } : opts || {};
		const request =
			String(o.type || "POST").toUpperCase() === "GET"
				? api.getCall(o.method, toQuery(o.args))
				: api.baseCall(o.method, o.args || {});
		const promise = request.then(
			(message) => {
				const r = { message };
				o.callback?.(r);
				return r;
			},
			(error) => {
				if (o.error) o.error(error);
				else onError?.(error);
				throw error;
			},
		);
		// A script that handles the outcome through callbacks must not leave an unhandled rejection.
		if (o.callback || o.error) promise.catch(() => {});
		return promise;
	}

	const message = (r) => r.message;
	const db = {
		get_list: (doctype, args = {}) =>
			call({
				method: "frappe.client.get_list",
				type: "GET",
				args: {
					doctype,
					fields: args.fields || ["name"],
					filters: args.filters,
					order_by: args.order_by,
					limit_start: args.limit_start,
					limit_page_length: "limit" in args ? args.limit : 20,
				},
			}).then(message),
		get_value: (doctype, filters, fieldname, callback) =>
			call({
				method: "frappe.client.get_value",
				type: "GET",
				args: { doctype, filters, fieldname },
				callback: callback && ((r) => callback(r.message)),
			}),
		get_doc: (doctype, name, filters) =>
			call({ method: "frappe.client.get", type: "GET", args: { doctype, name, filters } }).then(message),
		insert: (doc) => call({ method: "frappe.client.insert", args: { doc } }).then(message),
		set_value: (doctype, name, fieldname, value, callback) =>
			call({
				method: "frappe.client.set_value",
				args: { doctype, name, fieldname, value },
				callback: callback && ((r) => callback(r.message)),
			}),
		delete_doc: (doctype, name) => call({ method: "frappe.client.delete", args: { doctype, name } }).then(message),
	};

	const frappe = guard(
		{
			call,
			db: guard(db, "db", report),
			session: guard({ user: api.user }, "session", report),
			datetime: guard({ get_today: today, str_to_user: strToUser }, "datetime", report),
			format,
		},
		"",
		report,
	);
	UNSUPPORTED.set(frappe, unsupported);
	return frappe;
}

/**
 * Run a page script against `rootElement`, as Desk's create_shadow_element does.
 *
 * @returns {{ok: boolean, unsupported?: string, error?: Error}} `unsupported` names the first
 *   Desk member the script reached for while it ran; `error` is what it threw.
 */
export function runPageScript(script, rootElement, standIn, fac = {}) {
	const seen = UNSUPPORTED.get(standIn) || [];
	const before = seen.length;
	let error = null;
	try {
		new Function("root_element", "frappe", "__", "fac", script || "")(rootElement, standIn, __, fac);
	} catch (e) {
		error = e;
	}
	const result = { ok: !error };
	if (seen.length > before) result.unsupported = seen[before];
	if (error) result.error = error;
	return result;
}
