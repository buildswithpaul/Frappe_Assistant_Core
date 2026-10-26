/**
 * Narrows what a personal page's script can reach beyond its frame's policy. CSP does not govern
 * WebRTC, so a peer connection to a server the script names could carry data out; the runtime
 * removes it before the page's script runs. Elements the script inserts that load or embed
 * something are removed as they appear. Neither closes DNS or timing side channels.
 */

const WEBRTC = [
	"RTCPeerConnection",
	"webkitRTCPeerConnection",
	"RTCDataChannel",
	"RTCIceCandidate",
	"RTCSessionDescription",
	"RTCRtpSender",
	"RTCRtpReceiver",
	"RTCRtpTransceiver",
	"RTCDtlsTransport",
	"RTCIceTransport",
	"RTCSctpTransport",
	"RTCCertificate",
];

/** Removes WebRTC from `win`: each constructor, and the way back to it from its prototype. */
export function removeWebRtc(win) {
	for (const name of WEBRTC) {
		const Constructor = win[name];
		if (!Constructor) continue;
		try {
			Object.defineProperty(Constructor.prototype, "constructor", { value: undefined });
		} catch {
			// a frozen prototype keeps its constructor; the global still goes below
		}
		try {
			delete win[name];
		} catch {
			// not configurable: shadowed below
		}
		if (win[name]) Object.defineProperty(win, name, { value: undefined, configurable: false, writable: false });
	}
}

const LOADING_TAGS = new Set(["link", "meta", "base", "iframe", "frame", "object", "embed", "portal"]);

/** Removes elements that load or embed something as soon as the script inserts them. */
export function removeLoadingElements(doc) {
	const sweep = (node) => {
		if (node.nodeType !== 1) return;
		if (LOADING_TAGS.has(node.localName)) node.remove();
		else node.querySelectorAll?.([...LOADING_TAGS].join(",")).forEach((el) => el.remove());
	};
	const observer = new doc.defaultView.MutationObserver((records) => {
		for (const record of records) record.addedNodes.forEach(sweep);
	});
	// The whole document, head included, where a script could add a preconnect link.
	observer.observe(doc.documentElement, { childList: true, subtree: true });
	return observer;
}
