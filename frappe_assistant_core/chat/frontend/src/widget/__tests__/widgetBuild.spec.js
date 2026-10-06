// @vitest-environment node
// A real Vite build needs esbuild, which rejects the TextEncoder of the default jsdom env.
import { describe, it, expect } from "vitest";
import { build } from "vite";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

describe("widget build", () => {
	it("emits a manifest with the launcher entry, one stylesheet, and no frappe-ui", async () => {
		await build({ configFile: resolve(process.cwd(), "vite.widget.config.js"), logLevel: "silent" });
		const out = resolve(process.cwd(), "../../public/chat/widget-app");
		const manifest = JSON.parse(readFileSync(resolve(out, ".vite/manifest.json"), "utf8"));
		const entry = manifest["src/widget/main.js"];
		expect(entry && entry.isEntry).toBe(true);
		// cssCodeSplit:false lists the stylesheet as its own record, not under a chunk's `css`.
		const css = Object.values(manifest).flatMap((r) => (r.file.endsWith(".css") ? [r.file] : r.css || []));
		expect(new Set(css).size).toBe(1);
		const js = Object.values(manifest)
			.filter((r) => r.file.endsWith(".js"))
			.map((r) => readFileSync(resolve(out, r.file), "utf8"))
			.join("\n");
		expect(js).not.toMatch(/reka-ui/);
		expect(existsSync(resolve(out, entry.file))).toBe(true);
	}, 120000);
});
