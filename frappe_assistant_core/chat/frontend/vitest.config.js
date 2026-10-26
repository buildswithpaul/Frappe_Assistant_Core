import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath } from "node:url";

import { fsAllow } from "./build/fsAllow.js";

export default defineConfig({
	plugins: [vue()],
	test: {
		environment: "jsdom",
		globals: true,
		// Vitest blanks every stylesheet by default, including ?raw imports; MockupFrame inlines the
		// kit, and PageView's spec reads the page box's containment from its computed style.
		css: { include: [/mockup_kit\.css/, /PageView\.vue/] },
		include: ["src/**/*.spec.js"],
	},
	server: { fs: { allow: fsAllow } },
	resolve: {
		alias: {
			"@": fileURLToPath(new URL("./src", import.meta.url)),
		},
	},
});
