import { detectContext } from "../desk/pageContext.js";

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
