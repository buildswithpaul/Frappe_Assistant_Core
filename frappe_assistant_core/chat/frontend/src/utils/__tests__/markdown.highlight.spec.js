import { describe, it, expect } from "vitest";
import { renderMarkdown, ensureHljs } from "@/utils/markdown";

describe("code highlighting", () => {
	it("highlights a python block once highlight.js has loaded", async () => {
		await ensureHljs();
		const html = renderMarkdown("```python\ndef total(x):\n    return x\n```");
		expect(html).toMatch(/<span class="hljs-keyword">def<\/span>/);
		expect(html).toMatch(/class="hljs language-python"/);
	});

	it("escapes code in a language it does not know instead of guessing", async () => {
		await ensureHljs();
		const html = renderMarkdown("```nosuchlang\n<script>alert(1)</script>\n```");
		expect(html).toContain("&lt;script&gt;");
		expect(html).not.toMatch(/<script/i);
	});

	it("ships only the languages we chose, not all 190", async () => {
		const { default: hljs } = await import("@/utils/highlight");
		expect(hljs.listLanguages().sort()).toEqual(
			["bash", "css", "javascript", "json", "python", "sql", "xml", "yaml"].sort()
		);
	});
});
