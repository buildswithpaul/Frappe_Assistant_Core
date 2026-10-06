import { describe, it, expect } from "vitest";
import { renderMarkdown } from "@/utils/markdown";

const TABLE = [
	"| Invoice | Customer | Outstanding |",
	"|---|---|---:|",
	"| ACC-SINV-0041 | Acme Corp | 12,500.00 |",
].join("\n");

describe("tables", () => {
	it("wraps every table in a horizontal scroll container", () => {
		const html = renderMarkdown(TABLE);
		expect(html).toMatch(/<div class="md-table-scroll"><table>/);
	});

	it("keeps identifier-like cells on one line", () => {
		const html = renderMarkdown(TABLE);
		expect(html).toMatch(/<td class="md-nowrap">ACC-SINV-0041<\/td>/);
		expect(html).toMatch(/<td align="right" class="md-nowrap">12,500.00<\/td>/);
	});

	it("lets prose cells wrap", () => {
		const html = renderMarkdown(TABLE);
		expect(html).toMatch(/<td>Acme Corp<\/td>/);
	});
});
