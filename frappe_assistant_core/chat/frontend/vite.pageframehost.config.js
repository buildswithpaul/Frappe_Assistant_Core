import { defineConfig } from "vite";
import { resolve } from "path";

// The host side of a personal page's frame (src/utils/pageFrameHost.js) for the fac-pages Desk
// page, which cannot import a module: one classic script that sets window.fac_page_frame_host.
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
			entry: resolve(import.meta.dirname, "src/utils/pageFrameHost.js"),
			name: "fac_page_frame_host",
			formats: ["iife"],
			fileName: () => "fac_page_frame_host.js",
		},
	},
});
