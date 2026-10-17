import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { readFileSync } from "fs";
import { resolve } from "path";
import frappeui from "frappe-ui/vite";
import { VitePWA } from "vite-plugin-pwa";
import { keepFirstScreen } from "./build/pwaPrecache.js";

const OUT_DIR = resolve(import.meta.dirname, "../../public/chat/spa");
const SPA_BASE = "/assets/frappe_assistant_core/chat/spa/";

export default defineConfig({
	plugins: [
		frappeui({
			frappeProxy: true,
			lucideIcons: false,
			jinjaBootData: true,
			buildConfig: {
				indexHtmlPath: "../../www/copilot.html",
				emptyOutDir: true,
				// No sourcemaps. Frappe serves everything under public/ statically, so a
				// shipped .map hands out the full source of a proprietary app; "hidden"
				// only drops the sourceMappingURL comment and still leaves the file
				// fetchable. Build locally with sourcemap:true to symbolize a stack trace.
				sourcemap: false,
				outDir: "../../public/chat/spa",
				baseUrl: SPA_BASE,
			},
		}),
		vue(),
		// Installable app (PWA), following Raven's setup. The manifest and offline page
		// are static files in public/; the worker is src/sw.js, served at /copilot/sw.js
		// by chat/service_worker.py so its scope covers the SPA's pages.
		VitePWA({
			strategies: "injectManifest",
			srcDir: "src",
			filename: "sw.js",
			injectRegister: false, // registered in src/utils/serviceWorker.js
			manifest: false, // public/manifest.webmanifest, linked from index.html
			injectManifest: {
				globPatterns: ["**/*.{js,css,html,woff2,png,svg,webmanifest}"],
				// The built index.html is an unrendered Jinja shell; the page comes from /copilot.
				globIgnores: ["index.html"],
				// Precache entries are relative to the build directory; the page requests
				// them under the asset base.
				modifyURLPrefix: { "": SPA_BASE },
				manifestTransforms: [
					async (entries) => {
						const viteManifest = JSON.parse(readFileSync(`${OUT_DIR}/.vite/manifest.json`, "utf8"));
						return { manifest: keepFirstScreen(entries, viteManifest, SPA_BASE) };
					},
				],
				maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
			},
			devOptions: { enabled: false },
		}),
	],
	resolve: {
		alias: {
			"@": resolve(import.meta.dirname, "src"),
		},
	},
	build: {
		rolldownOptions: {
			// frappe-ui internally imports ~icons/lucide/* (unplugin-icons) in some
			// components (Toast, etc.). When lucideIcons is disabled these can't be
			// resolved — mark them as external so the build doesn't fail.
			external: (id) => id.startsWith("~icons/"),
			output: {
				// Use proper naming for long-term caching
				chunkFileNames: "assets/[name].[hash].js",
				entryFileNames: "assets/[name].[hash].js",
				assetFileNames: "assets/[name].[hash].[ext]",
			},
		},
		// Generate manifest for dynamic chunk resolution
		manifest: true,
		// Ensure proper target for modern browsers
		target: "es2015",
	},
});
