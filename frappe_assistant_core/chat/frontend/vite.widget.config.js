import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";
import { postcssShadowHost } from "./build/postcssShadowHost.js";
import { widgetGuards } from "./build/widgetGuards.js";

// The Desk widget: launcher entry (no Vue) that lazily imports the Vue panel.
// Everything renders inside shadow roots, so CSS is one file the panel links
// into its own root, retargeted from :root/[data-theme] to :host.
export default defineConfig({
	base: "/assets/frappe_assistant_core/chat/widget-app/",
	plugins: [widgetGuards(), vue()],
	resolve: {
		// Exact matches: the object form prefix-matches, which would rewrite subpath imports
		// such as vue-echarts/dist/csp/style.css.
		alias: [
			{ find: /^@\//, replacement: resolve(__dirname, "src") + "/" },
			{ find: /^frappe-ui$/, replacement: resolve(__dirname, "build/frappeUiCallShim.js") },
			{
				find: /^vue-echarts$/,
				replacement: resolve(__dirname, "node_modules/vue-echarts/dist/csp/index.esm.js"),
			},
		],
	},
	css: { postcss: { plugins: [postcssShadowHost()] } },
	build: {
		outDir: resolve(__dirname, "../../public/chat/widget-app"),
		emptyOutDir: true,
		manifest: true,
		cssCodeSplit: false,
		sourcemap: false,
		target: "es2019",
		rollupOptions: {
			input: { main: resolve(__dirname, "src/widget/main.js") },
			// widget_loader.js calls the entry's boot(); Vite defaults to dropping entry exports.
			preserveEntrySignatures: "exports-only",
			external: (id) => id.startsWith("~icons/"),
			output: {
				entryFileNames: "assets/[name].[hash].js",
				chunkFileNames: "assets/[name].[hash].js",
				assetFileNames: "assets/[name].[hash].[ext]",
			},
		},
	},
});
