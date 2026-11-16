/**
 * What an open page has shown that FAC's read tools hide from FACO, so FACO's screenshot can look
 * without asking when the answer is nothing.
 *
 * A page's script reads in the user's own session, outside the masking FAC's tools apply
 * (core/security_config.py SENSITIVE_FIELDS). Every call the page makes passes through `watch`,
 * which checks the answer's field names against get_page's `withheld`.
 */
import { PAGE_API_CHECK, PAGE_READ_METHODS } from "./pageFrameHost";
import { RECORD_WRITES } from "./pageRequestPrompt";

// Frappe's own reads and writes answer with records, whose field names say what they hold.
const CHECKABLE_METHODS = new Set([...PAGE_READ_METHODS, ...RECORD_WRITES, PAGE_API_CHECK]);
// How far into an answer, and how many values, are searched for field names.
const MAX_DEPTH = 6;
const MAX_NODES = 50000;

const isBlank = (value) => value === null || value === undefined || value === "";

/**
 * @param {{fields: string[], doctypes: Object<string, string[]>, hidden_doctypes: string[]}|undefined} withheld
 *   get_page's `withheld`; without it nothing can be told, as from an older server.
 */
export function createPageReach(withheld) {
	const known = withheld && Array.isArray(withheld.fields);
	const everywhere = new Set(known ? withheld.fields : []);
	const hiddenDoctypes = new Set(known ? withheld.hidden_doctypes || [] : []);
	const hidesAnything =
		everywhere.size > 0 || hiddenDoctypes.size > 0 || Object.keys(known ? withheld.doctypes || {} : {}).length > 0;
	const fields = new Set();
	const methods = new Set();

	function findFields(answer, hidden) {
		let nodes = 0;
		const visit = (value, depth) => {
			if (value === null || typeof value !== "object" || depth > MAX_DEPTH || ++nodes > MAX_NODES) return;
			if (Array.isArray(value)) {
				value.forEach((item) => visit(item, depth + 1));
				return;
			}
			// A report's column, and a list view's keys, name a field without holding its value.
			if (typeof value.fieldname === "string" && hidden.has(value.fieldname)) fields.add(value.fieldname);
			if (Array.isArray(value.keys)) value.keys.forEach((key) => hidden.has(key) && fields.add(key));
			for (const [key, item] of Object.entries(value)) {
				if (hidden.has(key) && !isBlank(item)) fields.add(key);
				visit(item, depth + 1);
			}
		};
		visit(answer, 0);
	}

	function note(method, args, answer) {
		if (!hidesAnything) return;
		if (!CHECKABLE_METHODS.has(method)) {
			methods.add(method);
			return;
		}
		const doctype = typeof args?.doctype === "string" ? args.doctype : "";
		if (hiddenDoctypes.has(doctype)) fields.add(doctype);
		findFields(answer, new Set([...everywhere, ...(withheld.doctypes?.[doctype] || [])]));
	}

	return {
		/** Hands back `request` unchanged, noting what its answer shows. */
		watch(method, args, request) {
			return request.then((answer) => {
				note(method, args, answer);
				return answer;
			});
		},
		/** What the page has shown that FACO's tools hide, or null when that can't be told. */
		shown: () => (known ? { fields: [...fields].sort(), methods: [...methods].sort() } : null),
	};
}
