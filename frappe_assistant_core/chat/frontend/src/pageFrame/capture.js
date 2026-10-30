/**
 * FACO's picture of a personal page, drawn inside the page's own frame.
 *
 * The page is copied with its computed styles written inline, wrapped in an SVG <foreignObject>,
 * loaded as an image from a data: URL and drawn onto a canvas. Only the image bytes leave the
 * frame. Nothing here can reach another server: an SVG used as an image loads no outside
 * resource, and the frame's policy (connect-src 'none', images only from the site) and its
 * sandbox block anything else. The site's own images may come out blank, which is accepted.
 */

import { fitScreenshot } from "@/utils/screenshotFit";

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

// A box's computed size is the size it took on the live page. Written into the picture, it would
// freeze every box at that size while the text inside reflows a little differently, so a card cut
// off its last rows and a grid pushed its last tile off the edge. Only a size the page itself wrote
// is kept, as written, and the rest of the layout sizes itself as it did on the page.
const SIZES = new Set([
	"width",
	"height",
	"min-width",
	"min-height",
	"max-width",
	"max-height",
	"inline-size",
	"block-size",
	"min-inline-size",
	"min-block-size",
	"max-inline-size",
	"max-block-size",
]);
// Media keep their drawn size: without it an image or a chart's canvas has no box at all.
const REPLACED = new Set(["img", "svg", "canvas", "video", "picture", "input", "select", "textarea", "button"]);

// The size declarations in the page's own style sheets, read once per picture.
function sizeRules(doc) {
	const rules = [];
	const visit = (list) => {
		for (const rule of list || []) {
			if (rule.cssRules && !rule.selectorText) visit(rule.cssRules);
			if (!rule.selectorText || !rule.style) continue;
			const sizes = [];
			for (const property of SIZES) {
				const value = rule.style.getPropertyValue(property);
				if (value) sizes.push([property, value]);
			}
			if (sizes.length) rules.push({ selector: rule.selectorText, sizes });
		}
	};
	for (const sheet of doc.styleSheets) {
		try {
			visit(sheet.cssRules);
		} catch {
			// A sheet the frame can't read adds nothing.
		}
	}
	return rules;
}

// The sizes the page wrote for this element: its style sheets in order, then its own style attribute.
function authoredSizes(element, rules) {
	const sizes = new Map();
	for (const { selector, sizes: declared } of rules) {
		let matches = false;
		try {
			matches = element.matches(selector);
		} catch {
			// A selector this element can't be tested against, such as ::before, sets nothing.
		}
		if (matches) for (const [property, value] of declared) sizes.set(property, value);
	}
	for (const property of SIZES) {
		const value = element.style.getPropertyValue(property);
		if (value) sizes.set(property, value);
	}
	return sizes;
}

function inlineStyle(element, rules, isRoot = false) {
	const computed = getComputedStyle(element);
	const base = defaultStyle(element);
	const keepsComputedSize = REPLACED.has(element.localName);
	const parts = isRoot ? INHERITED.map((property) => `${property}:${computed.getPropertyValue(property)}`) : [];
	for (let i = 0; i < computed.length; i++) {
		const property = computed[i];
		if (SIZES.has(property) && !keepsComputedSize) continue;
		const value = computed.getPropertyValue(property);
		if (value !== base[property] && !(isRoot && INHERITED.includes(property))) parts.push(`${property}:${value}`);
	}
	if (!keepsComputedSize) {
		for (const [property, value] of authoredSizes(element, rules)) parts.push(`${property}:${value}`);
	}
	// The picture's root is as wide as the live page, so its content wraps where the page's did.
	if (isRoot) parts.push(`width:${element.getBoundingClientRect().width}px`);
	return parts.join(";");
}

export function copyWithStyles(root) {
	const rules = sizeRules(root.ownerDocument);
	let count = 0;
	const walk = (node) => {
		if (node.nodeType === Node.TEXT_NODE) return node.cloneNode(false);
		if (node.nodeType !== Node.ELEMENT_NODE || SKIP.has(node.localName)) return null;
		if (++count > MAX_ELEMENTS) throw new Error("The page is too large to capture.");
		const copy = node.cloneNode(false);
		// SVG keeps its drawing attributes; only its outer box needs the page's layout.
		const isSvgChild = node instanceof SVGElement && node.localName !== "svg";
		if (!isSvgChild) copy.setAttribute("style", inlineStyle(node, rules, node === root));
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
 * Draw `root` as a JPEG inside this frame, scaled or cut to fit a model's size limit
 * (utils/screenshotFit).
 *
 * @returns {Promise<{buffer: ArrayBuffer, width: number, height: number, page_width: number,
 *   page_height: number}>} the picture, its size and the page's own CSS size
 * @throws when the browser taints the canvas or cannot draw the page
 */
export async function capturePage(root, { scale = 1, quality = 80 } = {}) {
	const width = Math.max(1, Math.ceil(root.scrollWidth));
	const pageHeight = Math.max(1, Math.ceil(root.scrollHeight));
	const fit = fitScreenshot({ width, height: pageHeight, scale: Math.min(Math.max(Number(scale) || 1, 0.5), 2) });
	// The picture's own height: the SVG shows only this much of the page, from the top.
	const height = fit.height;
	const markup = new XMLSerializer().serializeToString(copyWithStyles(root));
	const svg =
		`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">` +
		`<foreignObject x="0" y="0" width="100%" height="100%">${markup}</foreignObject></svg>`;
	// A data: URL, not a blob: one: in an opaque-origin frame Chrome taints a canvas drawn from a
	// blob: image, and a tainted canvas cannot be exported.
	const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
	const image = await loadImage(url);
	const canvas = document.createElement("canvas");
	const ratio = fit.scale;
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
	return {
		buffer: await blob.arrayBuffer(),
		width: canvas.width,
		height: canvas.height,
		page_width: width,
		page_height: pageHeight,
	};
}
