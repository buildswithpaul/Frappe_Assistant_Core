import { describe, expect, it } from "vitest";

import { guardLoadingElements, removeLoadingElements, removeWebRtc } from "./hardening";

describe("removeWebRtc", () => {
	it("removes each WebRTC constructor and the way back to it from its prototype", () => {
		class RTCPeerConnection {}
		class RTCDataChannel {}
		const win = { RTCPeerConnection, webkitRTCPeerConnection: RTCPeerConnection, RTCDataChannel, fetch: () => {} };
		const proto = RTCPeerConnection.prototype;
		removeWebRtc(win);
		expect(win.RTCPeerConnection).toBeUndefined();
		expect(win.webkitRTCPeerConnection).toBeUndefined();
		expect(win.RTCDataChannel).toBeUndefined();
		expect(proto.constructor).toBeUndefined();
		expect(typeof win.fetch).toBe("function");
	});

	it("shadows a constructor that cannot be deleted", () => {
		const win = {};
		Object.defineProperty(win, "RTCPeerConnection", { value: class {}, configurable: false, writable: true });
		removeWebRtc(win);
		expect(win.RTCPeerConnection).toBeUndefined();
	});
});

// A route nothing wraps, kept from before the guard, for the last net's test.
const unwrappedAppend = Node.prototype.appendChild;
// jsdom has no XSLT; Chrome does, and the guard must take it away.
window.XSLTProcessor = class XSLTProcessor {};
// The guard changes this test file's own window, as the runtime changes the page's frame.
guardLoadingElements(window);

// A template parses inertly, so its content still holds whatever the markup named.
function templateContent(html) {
	const template = document.createElement("template");
	template.innerHTML = html;
	return template.content;
}

describe("guardLoadingElements", () => {
	it("refuses to create elements that load, embed or connect", () => {
		for (const tag of ["iframe", "IFRAME", "link", "meta", "object", "embed", "frame", "base"]) {
			expect(() => document.createElement(tag), tag).toThrow(/cannot create/);
		}
		expect(() => document.createElementNS("http://www.w3.org/1999/xhtml", "iframe")).toThrow(/cannot create/);
		expect(document.createElement("div").localName).toBe("div");
	});

	it("strips them from markup set on an element, before the document sees them", () => {
		const box = document.createElement("div");
		document.body.append(box);
		box.innerHTML = '<p>kept</p><link rel="preconnect" href="https://evil.example"><iframe srcdoc="x"></iframe>';
		expect(box.innerHTML).toBe("<p>kept</p>");
		box.insertAdjacentHTML("beforeend", '<span>more</span><object data="x"></object>');
		expect(box.innerHTML).toBe("<p>kept</p><span>more</span>");
		box.firstChild.outerHTML = '<b>swapped</b><meta http-equiv="refresh" content="0">';
		expect(box.innerHTML).toBe("<b>swapped</b><span>more</span>");
		box.remove();
	});

	it("strips them from fragments and parsed documents too", () => {
		const fragment = document.createRange().createContextualFragment('<i>x</i><link rel="preload" href="https://evil.example/a">');
		expect(fragment.querySelector("link")).toBeNull();
		const parsed = new DOMParser().parseFromString('<p>y</p><iframe src="https://evil.example"></iframe>', "text/html");
		expect(parsed.querySelector("iframe")).toBeNull();
	});

	it("gives a frame that got in no window to reach into, and refuses write and open on every document", () => {
		expect(Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, "contentWindow").get()).toBe(null);
		expect(Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, "contentDocument").get()).toBe(null);
		expect(() => document.write("<iframe></iframe>")).toThrow(/cannot create/);
		expect(() => document.open()).toThrow(/cannot create/);
		const other = document.implementation.createHTMLDocument("x");
		expect(() => other.writeln("<link>")).toThrow(/cannot create/);
	});

	it("strips nodes built elsewhere as they are inserted, imported, adopted or cloned", () => {
		const box = document.createElement("div");
		document.body.append(box);
		const markup = '<p>kept</p><link rel="preconnect" href="https://evil.example"><iframe></iframe>';
		box.append(templateContent(markup));
		box.appendChild(templateContent(markup));
		box.insertBefore(templateContent(markup), box.firstChild);
		box.firstChild.replaceWith(templateContent(markup));
		box.prepend(document.importNode(templateContent(markup), true));
		box.append(templateContent(markup).cloneNode(true));
		const other = document.implementation.createHTMLDocument("x");
		const holder = other.createElement("template");
		holder.innerHTML = markup;
		box.append(document.adoptNode(holder.content));
		const range = document.createRange();
		range.setStart(box, 0);
		range.insertNode(templateContent(markup));
		expect(box.querySelector("link, iframe")).toBeNull();
		expect(box.querySelectorAll("p").length).toBeGreaterThan(5);
		box.remove();
	});

	it("strips a node as it is imported or cloned, before it is inserted anywhere", () => {
		const markup = '<p>kept</p><link rel="preconnect" href="https://evil.example">';
		expect(document.importNode(templateContent(markup), true).querySelector("link")).toBeNull();
		expect(templateContent(markup).cloneNode(true).querySelector("link")).toBeNull();
	});

	it("leaves the page no XSLT to build elements with", () => {
		expect(window.XSLTProcessor).toBeUndefined();
	});
});

describe("removeLoadingElements", () => {
	it("removes loading elements that reach the document by another way", async () => {
		const observer = removeLoadingElements(document);
		try {
			// A route the guard does not wrap still lands the element; the observer takes it out.
			unwrappedAppend.call(document.body, templateContent('<embed src="x">'));
			await Promise.resolve();
			expect(document.querySelector("embed")).toBeNull();
		} finally {
			observer.disconnect();
		}
	});
});
