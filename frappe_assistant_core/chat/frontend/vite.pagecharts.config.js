import { defineConfig } from "vite";
import { resolve } from "path";

// fac.chart and fac.report for the fac-pages Desk page and a personal page's frame:
// utils/pageFacBundle.js as one classic script that sets window.fac_page_charts. The chat panel
// imports the same modules, so every host draws the same chart and reads a report the same way.
export default defineConfig({
	// public/ holds the SPA's PWA files; they do not belong next to Desk's scripts.
	publicDir: false,
	// Library mode leaves ECharts' process.env.NODE_ENV checks in, and a browser has no process.
	define: { "process.env.NODE_ENV": JSON.stringify("production") },
	resolve: {
		alias: [{ find: /^@\//, replacement: resolve(import.meta.dirname, "src") + "/" }],
	},
	build: {
		outDir: resolve(import.meta.dirname, "../../public/js"),
		// public/js also holds FAC's hand-written Desk scripts.
		emptyOutDir: false,
		sourcemap: false,
		target: "es2019",
		lib: {
			entry: resolve(import.meta.dirname, "src/utils/pageFacBundle.js"),
			name: "fac_page_charts",
			formats: ["iife"],
			fileName: () => "fac_page_charts.js",
		},
	},
});
