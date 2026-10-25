import { defineConfig } from "vite";
import { resolve } from "path";

// fac.chart for the fac-pages Desk page: utils/pageCharts.js as one classic script that sets
// window.fac_page_charts. The chat panel imports the same module, so both draw the same chart.
export default defineConfig({
	// public/ holds the SPA's PWA files; they do not belong next to Desk's scripts.
	publicDir: false,
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
			entry: resolve(import.meta.dirname, "src/utils/pageCharts.js"),
			name: "fac_page_charts",
			formats: ["iife"],
			fileName: () => "fac_page_charts.js",
		},
	},
});
