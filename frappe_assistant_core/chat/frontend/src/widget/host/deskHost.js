import { detectContext } from "../desk/pageContext.js";

// One navigation raises router change and form-refresh in quick succession.
const CONTEXT_DEBOUNCE_MS = 50;

/** Frappe Desk: the widget's original home, reached through Desk's own globals. */
export const deskHost = {
	name: "desk",
	clientType: "widget",
	browserTools: true,
	async init() {
		return true;
	},
	call(method, args = {}, type = "GET") {
		return window.frappe.call({ method, type, args });
	},
	user() {
		return (window.frappe && window.frappe.session && window.frappe.session.user) || null;
	},
	onRouteChange(fn) {
		const router = window.frappe && window.frappe.router;
		if (!router) return () => {};
		router.on("change", fn);
		return () => router.off && router.off("change", fn);
	},
	/**
	 * Fires once per navigation, after the page can be read. Desk raises the router `change`
	 * before a form's doc has loaded, so a form's own `form-refresh` is what carries the record.
	 */
	onContextChange(fn) {
		const stopRoute = this.onRouteChange(schedule);
		const $ = window.jQuery || window.$;
		if ($) $(document).on("form-refresh", schedule);
		let timer = null;
		function schedule() {
			clearTimeout(timer);
			timer = setTimeout(fn, CONTEXT_DEBOUNCE_MS);
		}
		return () => {
			clearTimeout(timer);
			stopRoute();
			if ($) $(document).off("form-refresh", schedule);
		};
	},
	isHiddenRoute() {
		const route = window.frappe && window.frappe.get_route ? window.frappe.get_route() : [];
		return Boolean(route && route[0] === "faco-assistant");
	},
	realtime() {
		return (window.frappe && window.frappe.realtime) || null;
	},
	detectContext() {
		return detectContext();
	},
	/** Desk answers page questions with its browser tools, so nothing rides on the message. */
	sendContext() {
		return null;
	},
	openDeskRoute(route) {
		window.frappe.set_route(...route);
	},
};
