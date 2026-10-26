/**
 * Runs inside a personal page's sandboxed frame (pageFrameDoc.js), built as the classic script
 * public/js/fac_page_frame.js (vite.pageframe.config.js).
 *
 * The frame has an opaque origin, so this is the page's only way to data: each call goes to the
 * host page by postMessage, and the host serves it as the user (pageFrameHost.js). The host also
 * asks here for the page's rendered markup, for Download PDF and for FACO's picture of the page.
 */
import { __ } from "@/utils/i18n";
import { snapshotHtml } from "@/utils/pagePrint";
import { makeFrappeStandIn } from "@/utils/pageRuntime";

import { removeLoadingElements, removeWebRtc } from "./hardening";

// Before anything of the page's runs: this script loads in the head, ahead of the page's own.
removeWebRtc(window);

// A page wider than this prints on a landscape sheet, as in the chat panel.
const WIDE_PAGE_PX = 900;

// The chat or Desk page: this frame sits inside the outer frame, which sits in the host.
const host = window.parent.parent;
const post = (message) => host.postMessage({ fac_page: 1, ...message }, "*");

const pending = new Map();
let nextId = 0;

function bridgeCall(method, args, type) {
	const id = ++nextId;
	return new Promise((resolve, reject) => {
		pending.set(id, { resolve, reject });
		post({ op: "call", id, method, args, type });
	});
}

function reportError(error) {
	post({ op: "error", message: String(error?.message || error || __("Unknown error")) });
}

const config = (() => {
	try {
		return JSON.parse(document.getElementById("fac-page-config")?.textContent || "{}");
	} catch {
		return {};
	}
})();

const frappe = makeFrappeStandIn(
	{ call: bridgeCall, user: config.user || "" },
	{ onUnsupported: (name) => post({ op: "unsupported", name: String(name) }), onError: reportError },
);

const fac = {
	chart(el, option) {
		const bundle = window.fac_page_charts;
		if (!bundle) throw new Error(__("Charts could not be loaded"));
		return bundle.chart(el, option);
	},
};

const root = () => document.querySelector(".fac-page-root") || document.body;

function snapshot({ id }) {
	const el = root();
	post({ op: "snapshot_result", id, html: snapshotHtml(el), wide: el.scrollWidth > WIDE_PAGE_PX });
}

window.addEventListener("message", (event) => {
	if (event.source !== host) return;
	const data = event.data;
	if (!data || data.fac_page !== 1) return;
	if (data.op === "reply") {
		const call = pending.get(data.id);
		if (!call) return;
		pending.delete(data.id);
		if (data.ok) call.resolve(data.message);
		else {
			const error = new Error(String(data.error?.message || __("The request failed")));
			error.status = data.error?.status || 0;
			call.reject(error);
		}
	} else if (data.op === "snapshot") snapshot(data);
});

window.addEventListener("error", (event) => reportError(event.error || event.message));
window.addEventListener("unhandledrejection", (event) => reportError(event.reason));

// The frame grows with the page on Desk, which scrolls it; the chat panel scrolls inside it.
let lastHeight = 0;
new ResizeObserver(() => {
	const height = document.documentElement.scrollHeight;
	if (height !== lastHeight) post({ op: "height", height: (lastHeight = height) });
}).observe(document.documentElement);

window.__fac_page = {
	run(fn) {
		removeLoadingElements(document);
		// Elsewhere root_element is a shadow root; here it is the page's own element, given the one
		// lookup a shadow root has and an element lacks.
		const element = root();
		element.getElementById = (elementId) => element.querySelector(`#${CSS.escape(String(elementId))}`);
		try {
			fn(element, frappe, __, fac);
		} catch (error) {
			reportError(error);
		}
		post({ op: "ready" });
	},
};
