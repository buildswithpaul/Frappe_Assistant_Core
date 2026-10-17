import { baseCall, getCall, getCsrfToken } from "@/api/_core.js";

const listeners = new Set();
let restoreHistory = null;
let user = null;

function notify() {
	for (const fn of listeners) {
		try {
			fn();
		} catch {
			// One listener's failure must not stop the others.
		}
	}
}

// SPAs route with history.pushState, which fires no event; wrap it while anyone listens.
function watchHistory() {
	const { pushState, replaceState } = window.history;
	window.history.pushState = function (...args) {
		const result = pushState.apply(this, args);
		notify();
		return result;
	};
	window.history.replaceState = function (...args) {
		const result = replaceState.apply(this, args);
		notify();
		return result;
	};
	window.addEventListener("popstate", notify);
	return () => {
		window.history.pushState = pushState;
		window.history.replaceState = replaceState;
		window.removeEventListener("popstate", notify);
	};
}

/** A standalone Frappe app (Helpdesk, Insights, CRM…): no frappe.boot, frappe.call or frappe.realtime. */
export const spaHost = {
	name: "spa",
	// The server offers browser tools only to "widget"; none of them can answer from this page.
	clientType: "spa",
	browserTools: false,
	/** Resolve the logged-in user once. False means the launcher must not mount. */
	async init() {
		if (!getCsrfToken()) return false;
		try {
			user = await getCall("frappe.auth.get_logged_user");
		} catch {
			user = null;
		}
		return Boolean(user && user !== "Guest");
	},
	async call(method, args = {}, type = "GET") {
		const message = type === "GET" ? await getCall(method, args) : await baseCall(method, args);
		return { message };
	},
	user() {
		return user;
	},
	/** The embedding page has no Desk forms to wait for, so it never changes context. */
	onContextChange() {
		return () => {};
	},
	onRouteChange(fn) {
		listeners.add(fn);
		if (!restoreHistory) restoreHistory = watchHistory();
		return () => {
			listeners.delete(fn);
			if (!listeners.size && restoreHistory) {
				restoreHistory();
				restoreHistory = null;
			}
		};
	},
	isHiddenRoute() {
		return false;
	},
	realtime() {
		return null;
	},
	detectContext() {
		return { type: "General" };
	},
	/** The page's path; the server turns it into one line naming the document, if any. */
	sendContext() {
		return { type: "app_page", path: window.location.pathname };
	},
	openDeskRoute(route, href) {
		window.open(href, "_blank", "noopener");
	},
};
