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

	it("measures decoded text, so an entity does not count as several characters", () => {
		const html = renderMarkdown("| Ref |\n|---|\n| AT&amp;T-0041 |");
		expect(html).toMatch(/<td class="md-nowrap">AT&amp;T-0041<\/td>/);
	});

	it("lets a cell wrap when markup surrounds one word of several", () => {
		const html = renderMarkdown("| Name |\n|---|\n| **Acme** Corp |");
		expect(html).toMatch(/<td><strong>Acme<\/strong> Corp<\/td>/);
	});
});
