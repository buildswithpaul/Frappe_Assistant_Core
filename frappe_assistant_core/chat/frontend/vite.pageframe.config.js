import { defineConfig } from "vite";
import { resolve } from "path";

// The runtime inside a personal page's sandboxed frame (src/pageFrame/runtime.js), as one classic
// script the frame loads from /assets. The chat panel and the fac-pages Desk page build that frame.
export default defineConfig({
	publicDir: false,
	define: { "process.env.NODE_ENV": JSON.stringify("production") },
	resolve: {
		alias: [{ find: /^@\//, replacement: resolve(import.meta.dirname, "src") + "/" }],
	},
	build: {
		outDir: resolve(import.meta.dirname, "../../public/js"),
		emptyOutDir: false,
		sourcemap: false,
		target: "es2019",
		lib: {
			entry: resolve(import.meta.dirname, "src/pageFrame/runtime.js"),
			name: "fac_page_frame",
			formats: ["iife"],
			fileName: () => "fac_page_frame.js",
		},
	},
});
