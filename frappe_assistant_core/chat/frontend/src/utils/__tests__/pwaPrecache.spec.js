import { describe, it, expect } from "vitest";
import { firstScreenFiles, keepFirstScreen } from "../../../build/pwaPrecache.js";

const BASE = "/assets/frappe_assistant_core/chat/spa/";

// Shape of Vite's .vite/manifest.json: an entry with a static import, CSS and
// fonts, plus lazily imported chunks the first screen never loads.
const viteManifest = {
	"index.html": {
		file: "assets/index.abc.js",
		isEntry: true,
		imports: ["_vendor.js"],
		css: ["assets/index.abc.css"],
		assets: ["assets/inter-400.woff2"],
		dynamicImports: ["src/MermaidDiagram.vue"],
	},
	"_vendor.js": { file: "assets/vendor.def.js", css: ["assets/vendor.def.css"] },
	"src/MermaidDiagram.vue": { file: "assets/MermaidDiagram.ghi.js", isDynamicEntry: true },
};

const entry = (file) => ({ url: `${BASE}${file}`, revision: null });

describe("firstScreenFiles", () => {
	it("follows static imports from the entry, with CSS and assets, but not lazy chunks", () => {
		expect([...firstScreenFiles(viteManifest)].sort()).toEqual(
			[
				"assets/index.abc.css",
				"assets/index.abc.js",
				"assets/inter-400.woff2",
				"assets/vendor.def.css",
				"assets/vendor.def.js",
			].sort()
		);
	});
});

describe("keepFirstScreen", () => {
	it("drops lazy chunks and keeps the first screen plus static files", () => {
		const entries = [
			"assets/index.abc.js",
			"assets/vendor.def.js",
			"assets/MermaidDiagram.ghi.js",
			"offline.html",
			"manifest.webmanifest",
			"icons/icon-192.png",
		].map(entry);
		const kept = keepFirstScreen(entries, viteManifest, BASE).map((e) => e.url.slice(BASE.length));
		expect(kept).toEqual([
			"assets/index.abc.js",
			"assets/vendor.def.js",
			"offline.html",
			"manifest.webmanifest",
			"icons/icon-192.png",
		]);
	});
});
