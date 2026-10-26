import { describe, expect, it } from "vitest";

import { removeLoadingElements, removeWebRtc } from "./hardening";

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

describe("removeLoadingElements", () => {
	it("removes elements that load or embed something as the script inserts them", async () => {
		const observer = removeLoadingElements(document);
		try {
			const box = document.createElement("div");
			box.innerHTML = '<p>kept</p><iframe srcdoc="x"></iframe><span><object data="x"></object></span>';
			document.body.append(box);
			const link = document.createElement("link");
			link.rel = "preconnect";
			link.href = "https://evil.example";
			document.head.append(link);
			await Promise.resolve();
			expect(document.querySelector("iframe, object, link[rel=preconnect]")).toBeNull();
			expect(box.querySelector("p").textContent).toBe("kept");
			box.remove();
		} finally {
			observer.disconnect();
		}
	});
});
