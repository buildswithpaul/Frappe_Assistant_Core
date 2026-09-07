import { describe, it, expect } from "vitest";
import { renderMarkdown, renderNotificationMarkdown } from "./markdown.js";

const XSS_PAYLOAD = "**bold** [link](https://example.com) <img src=x onerror=alert(1)>";

describe("renderMarkdown (chat path)", () => {
	it("strips event handlers but keeps <img> — chat needs images", () => {
		const html = renderMarkdown(XSS_PAYLOAD);
		expect(html).toContain("<strong>bold</strong>");
		expect(html).toContain('<a href="https://example.com">link</a>');
		expect(html).toContain("<img");
		expect(html).not.toContain("onerror");
	});
});

describe("renderNotificationMarkdown (notification path)", () => {
	it("strips <img> entirely, keeps other markdown", () => {
		const html = renderNotificationMarkdown(XSS_PAYLOAD);
		expect(html).toContain("<strong>bold</strong>");
		expect(html).toContain('<a href="https://example.com">link</a>');
		expect(html).not.toContain("<img");
		expect(html).not.toContain("onerror");
	});
});
