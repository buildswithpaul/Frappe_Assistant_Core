// Dev-only server for the harness pages in dev/ (dev/approval-card.html). `npm run build` uses
// vite.config.js and vite.widget.config.js, whose inputs don't include dev/, so nothing here ships.
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";

export default defineConfig({
	root: resolve(import.meta.dirname, ".."),
	plugins: [vue()],
	resolve: {
		alias: {
			"@": resolve(import.meta.dirname, "../src"),
		},
	},
	server: { strictPort: true },
});
