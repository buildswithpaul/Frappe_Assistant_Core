import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";
import frappeui from "frappe-ui/vite";

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
				baseUrl: "/assets/frappe_assistant_core/chat/spa/",
			},
		}),
		vue(),
	],
	resolve: {
		alias: {
			"@": resolve(__dirname, "src"),
		},
	},
	build: {
		rollupOptions: {
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
