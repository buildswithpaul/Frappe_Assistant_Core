/**
 * Narrows what a personal page's script can reach beyond its frame's policy, before it runs.
 *
 * - WebRTC is removed: CSP does not govern it, so a peer connection to a server the script names
 *   could carry data out. A child frame would be a fresh realm, but the frame's policy forbids
 *   child frames and objects (frame-src, child-src, object-src 'none'), a child of this
 *   opaque-origin frame would be cross-origin to it anyway, and frame elements are refused here.
 * - Elements that load, embed or start a connection (link, meta, base, frames, object, embed) are
 *   refused when created, and stripped from markup and from nodes on the insertion routes wrapped
 *   below, on the prototypes. Browsers keep adding ways to build nodes, so a route not wrapped
 *   here could still connect a <link rel="preconnect"> for a moment; a MutationObserver removes it
 *   right after. That falls within what remains: a deliberately malicious script can leak small
 *   amounts through DNS lookups, preconnects or timing, which no browser policy closes.
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

export const LOADING_TAGS = new Set(["link", "meta", "base", "iframe", "frame", "frameset", "object", "embed", "portal"]);
const LOADING_SELECTOR = [...LOADING_TAGS].join(",");

const refused = (tag) => new DOMException(`A page cannot create <${tag}> elements.`, "NotSupportedError");

function stripLoading(root) {
	if (root.nodeType === 1 && LOADING_TAGS.has(root.localName)) return null;
	root.querySelectorAll?.(LOADING_SELECTOR).forEach((el) => el.remove());
	return root;
}

// Markup parsed in an inert template, stripped, then inserted as nodes: nothing it names starts loading.
function parseClean(doc, html) {
	const template = doc.createElement("template");
	template.innerHTML = String(html);
	stripLoading(template.content);
	return template.content;
}

function wrapSetter(proto, property, wrap) {
	const descriptor = Object.getOwnPropertyDescriptor(proto, property);
	if (!descriptor?.set) return;
	Object.defineProperty(proto, property, { ...descriptor, set: wrap(descriptor.set) });
}

/**
 * Refuses elements that load or embed something, synchronously: at creation, when markup is set
 * or parsed, and as a frame's window. Call before the page's script runs.
 */
export function guardLoadingElements(win) {
	const { document: doc } = win;
	const proto = win.Document.prototype;
	const createElement = proto.createElement;
	proto.createElement = function (tag, options) {
		if (LOADING_TAGS.has(String(tag).toLowerCase())) throw refused(tag);
		return createElement.call(this, tag, options);
	};
	const createElementNS = proto.createElementNS;
	proto.createElementNS = function (ns, tag, options) {
		const local = String(tag).split(":").pop().toLowerCase();
		if (LOADING_TAGS.has(local)) throw refused(local);
		return createElementNS.call(this, ns, tag, options);
	};

	// Template parsing is inert, so the template's own innerHTML is left alone.
	const markupSetter = (set) =>
		function (html) {
			if (this.localName === "template") return set.call(this, html);
			this.replaceChildren(parseClean(doc, html));
		};
	wrapSetter(win.Element.prototype, "innerHTML", markupSetter);
	if (win.ShadowRoot) wrapSetter(win.ShadowRoot.prototype, "innerHTML", markupSetter);
	wrapSetter(win.Element.prototype, "outerHTML", () =>
		function (html) {
			this.replaceWith(parseClean(doc, html));
		},
	);
	const insertAdjacentHTML = win.Element.prototype.insertAdjacentHTML;
	win.Element.prototype.insertAdjacentHTML = function (position, html) {
		const where = { beforebegin: "before", afterbegin: "prepend", beforeend: "append", afterend: "after" }[
			String(position).toLowerCase()
		];
		if (!where) return insertAdjacentHTML.call(this, position, "");
		this[where](parseClean(doc, html));
	};
	const createContextualFragment = win.Range.prototype.createContextualFragment;
	win.Range.prototype.createContextualFragment = function (html) {
		return stripLoading(createContextualFragment.call(this, html));
	};
	const parseFromString = win.DOMParser.prototype.parseFromString;
	win.DOMParser.prototype.parseFromString = function (text, type) {
		const parsed = parseFromString.call(this, text, type);
		stripLoading(parsed);
		return parsed;
	};
	for (const name of ["write", "writeln", "open"]) {
		proto[name] = () => {
			throw refused(`document.${name}`);
		};
	}

	// setHTMLUnsafe parses like innerHTML; parseHTMLUnsafe builds a whole document from markup.
	for (const target of [win.Element?.prototype, win.ShadowRoot?.prototype]) {
		if (!target?.setHTMLUnsafe) continue;
		target.setHTMLUnsafe = function (html) {
			this.replaceChildren(parseClean(doc, html));
		};
	}
	if (win.Document.parseHTMLUnsafe) {
		const parseHTMLUnsafe = win.Document.parseHTMLUnsafe;
		win.Document.parseHTMLUnsafe = (html, options) => {
			const parsed = parseHTMLUnsafe.call(win.Document, html, options);
			stripLoading(parsed);
			return parsed;
		};
	}
	// XSLT can build any element from a stylesheet; a page has no use for it.
	try {
		delete win.XSLTProcessor;
	} catch {
		// shadowed below
	}
	if (win.XSLTProcessor) Object.defineProperty(win, "XSLTProcessor", { value: undefined });

	// Nodes built elsewhere (a template's content, another document, a clone) are stripped as they
	// are inserted, imported, adopted or cloned.
	const cleanNodes = (nodes) =>
		nodes.map((node) => {
			if (node?.nodeType === 1 && LOADING_TAGS.has(node.localName)) throw refused(node.localName);
			if (node?.nodeType) stripLoading(node);
			return node;
		});
	const wrapInsert = (target, name) => {
		const original = target?.[name];
		if (typeof original !== "function") return;
		target[name] = function (...nodes) {
			return original.apply(this, cleanNodes(nodes));
		};
	};
	for (const name of ["appendChild", "insertBefore", "replaceChild"]) wrapInsert(win.Node.prototype, name);
	for (const target of [win.Element.prototype, win.DocumentFragment.prototype, win.Document.prototype]) {
		for (const name of ["append", "prepend", "replaceChildren"]) wrapInsert(target, name);
	}
	for (const target of [win.Element.prototype, win.CharacterData.prototype, win.DocumentType?.prototype]) {
		for (const name of ["before", "after", "replaceWith"]) wrapInsert(target, name);
	}
	const wrapResult = (target, name) => {
		const original = target?.[name];
		if (typeof original !== "function") return;
		target[name] = function (...args) {
			const result = original.apply(this, args);
			if (result?.nodeType === 1 && LOADING_TAGS.has(result.localName)) throw refused(result.localName);
			if (result?.nodeType) stripLoading(result);
			return result;
		};
	};
	wrapInsert(win.Element.prototype, "insertAdjacentElement");
	wrapInsert(win.Range.prototype, "insertNode");
	wrapInsert(win.Range.prototype, "surroundContents");
	wrapResult(win.Node.prototype, "cloneNode");
	wrapResult(win.Document.prototype, "importNode");
	wrapResult(win.Document.prototype, "adoptNode");

	// A frame that got in anyway gives no window or document to reach into.
	for (const name of ["HTMLIFrameElement", "HTMLFrameElement", "HTMLObjectElement", "HTMLEmbedElement"]) {
		const element = win[name];
		if (!element) continue;
		for (const property of ["contentWindow", "contentDocument", "getSVGDocument"]) {
			if (property in element.prototype) {
				Object.defineProperty(element.prototype, property, { get: () => null, configurable: false });
			}
		}
	}
}

/** The last net: removes loading elements that reach the document anyway, as they appear. */
export function removeLoadingElements(doc) {
	const sweep = (node) => {
		if (node.nodeType !== 1) return;
		if (LOADING_TAGS.has(node.localName)) node.remove();
		else node.querySelectorAll?.(LOADING_SELECTOR).forEach((el) => el.remove());
	};
	const observer = new doc.defaultView.MutationObserver((records) => {
		for (const record of records) record.addedNodes.forEach(sweep);
	});
	// The whole document, head included.
	observer.observe(doc.documentElement, { childList: true, subtree: true });
	return observer;
}
