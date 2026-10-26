import { defineConfig } from "vite";
import { resolve } from "path";

const FRONTEND = resolve(import.meta.dirname, "../..");

// Builds entry.js into dist/harness.js; run.mjs serves it with the frame runtime under /assets.
export default defineConfig({
	root: FRONTEND,
	publicDir: false,
	define: { "process.env.NODE_ENV": JSON.stringify("production") },
	resolve: { alias: [{ find: /^@\//, replacement: resolve(FRONTEND, "src") + "/" }] },
	build: {
		outDir: resolve(import.meta.dirname, "dist"),
		emptyOutDir: true,
		sourcemap: false,
		target: "es2019",
		lib: { entry: resolve(import.meta.dirname, "entry.js"), name: "leakCheck", formats: ["iife"], fileName: () => "harness.js" },
	},
});
