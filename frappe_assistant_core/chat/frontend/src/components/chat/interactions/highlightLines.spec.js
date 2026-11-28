import { describe, expect, it } from "vitest";
import { ensureHljs, highlightCode } from "@/utils/markdown";
import { highlightedLines } from "./highlightLines";

describe("highlightedLines", () => {
	it("keeps a token that runs over several lines coloured on each of them", async () => {
		await ensureHljs();
		const html = highlightCode('text = """first\n<b>if</b> second\nthird"""\nx = 1', "python");

		const lines = highlightedLines(html);

		expect(lines).toHaveLength(4);
		// The middle line is still inside the string: its words are not read as code.
		expect(lines[1]).toBe('<span class="hljs-string">&lt;b&gt;if&lt;/b&gt; second</span>');
		expect(lines[3]).toContain('<span class="hljs-number">1</span>');
		for (const line of lines) {
			expect((line.match(/<span/g) || []).length).toBe((line.match(/<\/span>/g) || []).length);
		}
	});

	it("leaves plain lines as they are", () => {
		expect(highlightedLines("a\n\nb")).toEqual(["a", "", "b"]);
	});
});
