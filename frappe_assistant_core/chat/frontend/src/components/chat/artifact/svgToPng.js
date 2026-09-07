/**
 * Serialize a rendered <svg> element to a high-DPI PNG data URL.
 *
 * SVGs are transparent; we fill white first so the PNG reads correctly when
 * pasted into light- or dark-themed documents. Scaling the backing canvas by
 * `pixelRatio` yields a retina-sharp raster from the vector source.
 *
 * @param {SVGElement} svgEl  A rendered <svg> DOM node.
 * @param {number} pixelRatio Output scale factor (e.g. 2 for retina).
 * @returns {Promise<string>} A `data:image/png;base64,...` URL.
 */
export function svgToPng(svgEl, pixelRatio = 2) {
	return new Promise((resolve, reject) => {
		if (!svgEl) {
			reject(new Error("svgToPng: no svg element provided"));
			return;
		}

		// Intrinsic size for a sharp raster. Prefer the viewBox (true authored
		// dimensions) because mermaid sets width="100%" under useMaxWidth, which
		// would otherwise parse to a tiny 100px canvas. Fall back to numeric
		// width/height attrs, then the rendered box.
		function intrinsicSize(el) {
			const vb = el.getAttribute("viewBox") || el.viewBox?.baseVal;
			if (typeof vb === "string") {
				const parts = vb.trim().split(/[\s,]+/).map(Number);
				if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
					return { width: parts[2], height: parts[3] };
				}
			} else if (vb && vb.width > 0 && vb.height > 0) {
				return { width: vb.width, height: vb.height };
			}
			return null;
		}

		const rect = svgEl.getBoundingClientRect?.() || { width: 0, height: 0 };
		const vbSize = intrinsicSize(svgEl);
		// A bare numeric width attr (not "100%") is also acceptable.
		const attrW = parseFloat(svgEl.getAttribute("width"));
		const attrH = parseFloat(svgEl.getAttribute("height"));
		const widthAttrIsNumeric =
			svgEl.getAttribute("width") != null && !/%/.test(svgEl.getAttribute("width"));
		const heightAttrIsNumeric =
			svgEl.getAttribute("height") != null && !/%/.test(svgEl.getAttribute("height"));

		const width =
			(vbSize && vbSize.width) ||
			(widthAttrIsNumeric && attrW) ||
			rect.width ||
			0;
		const height =
			(vbSize && vbSize.height) ||
			(heightAttrIsNumeric && attrH) ||
			rect.height ||
			0;

		const serialized = new XMLSerializer().serializeToString(svgEl);
		const svgBlob = new Blob([serialized], { type: "image/svg+xml;charset=utf-8" });
		const url = URL.createObjectURL(svgBlob);

		const img = new Image();
		img.onload = () => {
			try {
				const w = (width || img.width) * pixelRatio;
				const h = (height || img.height) * pixelRatio;
				const canvas = document.createElement("canvas");
				canvas.width = w;
				canvas.height = h;
				const ctx = canvas.getContext("2d");
				if (!ctx) {
					URL.revokeObjectURL(url);
					reject(new Error("svgToPng: 2d canvas context unavailable"));
					return;
				}
				ctx.fillStyle = "#ffffff";
				ctx.fillRect(0, 0, w, h);
				ctx.drawImage(img, 0, 0, w, h);
				URL.revokeObjectURL(url);
				resolve(canvas.toDataURL("image/png"));
			} catch (e) {
				URL.revokeObjectURL(url);
				reject(e);
			}
		};
		img.onerror = (e) => {
			URL.revokeObjectURL(url);
			reject(e instanceof Error ? e : new Error("svgToPng: image load failed"));
		};
		img.src = url;
	});
}
