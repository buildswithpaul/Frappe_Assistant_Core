/**
 * FACO's picture of a personal page, drawn inside the page's own frame.
 *
 * The page is copied with its computed styles written inline, wrapped in an SVG <foreignObject>,
 * loaded as an image from a data: URL and drawn onto a canvas. Only the image bytes leave the
 * frame. Nothing here can reach another server: an SVG used as an image loads no outside
 * resource, and the frame's policy (connect-src 'none', images only from the site) and its
 * sandbox block anything else. The site's own images may come out blank, which is accepted.
 */

// More elements than this makes a picture too large to draw.
const MAX_ELEMENTS = 5000;
// What the page's text check keeps: the start of the visible text, figures and table cells included.
const MAX_TEXT = 6000;
// Elements that are not part of the picture.
const SKIP = new Set(["script", "style", "link", "meta", "base", "iframe", "frame", "object", "embed", "template", "noscript"]);

const defaults = new Map();

// The styles an element of this kind gets with no rules of its own, from a hidden copy in the same
// document, so the picture carries only the declarations that differ.
function defaultStyle(element) {
	const key = element.localName;
	if (defaults.has(key)) return defaults.get(key);
	const sample = element.ownerDocument.createElement(key);
	sample.style.cssText = "position:absolute;visibility:hidden;";
	element.ownerDocument.body.append(sample);
	const computed = getComputedStyle(sample);
	const values = {};
	for (let i = 0; i < computed.length; i++) values[computed[i]] = computed.getPropertyValue(computed[i]);
	sample.remove();
	defaults.set(key, values);
	return values;
}

// What the page inherits from its document, which the picture has none of: given to its root.
const INHERITED = ["font-family", "font-size", "font-weight", "font-style", "line-height", "color", "letter-spacing"];

function inlineStyle(element, isRoot = false) {
	const computed = getComputedStyle(element);
	const base = defaultStyle(element);
	const parts = isRoot ? INHERITED.map((property) => `${property}:${computed.getPropertyValue(property)}`) : [];
	for (let i = 0; i < computed.length; i++) {
		const property = computed[i];
		const value = computed.getPropertyValue(property);
		if (value !== base[property] && !(isRoot && INHERITED.includes(property))) parts.push(`${property}:${value}`);
	}
	return parts.join(";");
}

export function copyWithStyles(root) {
	let count = 0;
	const walk = (node) => {
		if (node.nodeType === Node.TEXT_NODE) return node.cloneNode(false);
		if (node.nodeType !== Node.ELEMENT_NODE || SKIP.has(node.localName)) return null;
		if (++count > MAX_ELEMENTS) throw new Error("The page is too large to capture.");
		const copy = node.cloneNode(false);
		// SVG keeps its drawing attributes; only its outer box needs the page's layout.
		const isSvgChild = node instanceof SVGElement && node.localName !== "svg";
		if (!isSvgChild) copy.setAttribute("style", inlineStyle(node, node === root));
		if (node.localName === "input") copy.setAttribute("value", node.value);
		if (node.localName === "textarea") copy.textContent = node.value;
		if (node.localName !== "textarea") {
			for (const child of node.childNodes) {
				const part = walk(child);
				if (part) copy.append(part);
			}
		}
		return copy;
	};
	return walk(root);
}

function loadImage(url) {
	return new Promise((resolve, reject) => {
		const image = new Image();
		image.onload = () => resolve(image);
		image.onerror = () => reject(new Error("The picture could not be drawn."));
		image.src = url;
	});
}

/** The page's visible text, trimmed: what FACO checks when it can't read the picture. */
export function pageText(root) {
	const text = (root.innerText ?? root.textContent ?? "").replace(/\n{3,}/g, "\n\n").trim();
	return text.length > MAX_TEXT ? `${text.slice(0, MAX_TEXT)}…` : text;
}

/**
 * Draw `root` as a JPEG inside this frame.
 *
 * @returns {Promise<{buffer: ArrayBuffer, width: number, height: number}>}
 * @throws when the browser taints the canvas or cannot draw the page
 */
export async function capturePage(root, { scale = 1, quality = 80 } = {}) {
	const width = Math.max(1, Math.ceil(root.scrollWidth));
	const height = Math.max(1, Math.ceil(root.scrollHeight));
	const markup = new XMLSerializer().serializeToString(copyWithStyles(root));
	const svg =
		`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">` +
		`<foreignObject x="0" y="0" width="100%" height="100%">${markup}</foreignObject></svg>`;
	// A data: URL, not a blob: one: in an opaque-origin frame Chrome taints a canvas drawn from a
	// blob: image, and a tainted canvas cannot be exported.
	const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
	const image = await loadImage(url);
	const canvas = document.createElement("canvas");
	const ratio = Math.min(Math.max(Number(scale) || 1, 0.5), 2);
	canvas.width = Math.round(width * ratio);
	canvas.height = Math.round(height * ratio);
	const context = canvas.getContext("2d");
	context.fillStyle = "#ffffff";
	context.fillRect(0, 0, canvas.width, canvas.height);
	context.scale(ratio, ratio);
	context.drawImage(image, 0, 0);
	const q = Math.min(Math.max(Number(quality) || 80, 10), 100) / 100;
	// A tainted canvas throws here; a canvas past the browser's limit gives null.
	const blob = await new Promise((resolve, reject) => {
		try {
			canvas.toBlob(resolve, "image/jpeg", q);
		} catch (error) {
			reject(error);
		}
	});
	if (!blob) throw new Error("The page is too large to capture.");
	return { buffer: await blob.arrayBuffer(), width: canvas.width, height: canvas.height };
}
