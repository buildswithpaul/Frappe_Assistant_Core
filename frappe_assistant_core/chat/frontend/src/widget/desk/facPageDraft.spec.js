import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, it, expect } from "vitest";

// The Desk page inlines this plain script with Frappe's render_include, so the test loads it the same way:
// as source text, evaluated for the functions it declares.
const SOURCE = readFileSync(
	resolve(import.meta.dirname, "../../../../../assistant_core/page/fac_pages/fac_page_draft.js"),
	"utf-8",
);
const { fac_page_draft_srcdoc, fac_page_draft_frame } = new Function(
	`${SOURCE}\nreturn { fac_page_draft_srcdoc, fac_page_draft_frame };`,
)();

const CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:";

function parse(srcdoc) {
	return new DOMParser().parseFromString(srcdoc, "text/html");
}

describe("fac_page_draft_srcdoc", () => {
	const srcdoc = fac_page_draft_srcdoc({
		html: '<div class="mk-card">Plan</div>',
		style: ".mk-card { color: red; }",
		kit_css: ".mk-kit { gap: 8px; }",
	});

	it("puts the Content-Security-Policy meta first in the head", () => {
		const first = parse(srcdoc).head.firstElementChild;
		expect(first.tagName).toBe("META");
		expect(first.getAttribute("http-equiv")).toBe("Content-Security-Policy");
		expect(first.getAttribute("content")).toBe(CSP);
		expect(srcdoc.indexOf("Content-Security-Policy")).toBeLessThan(srcdoc.indexOf("<style>"));
	});

	it("inlines the kit, then the draft's style, and wraps the html in the kit root", () => {
		const doc = parse(srcdoc);
		const css = doc.head.querySelector("style").textContent;
		expect(css).toContain(".mk-kit { gap: 8px; }");
		expect(css.indexOf(".mk-kit { gap: 8px; }")).toBeLessThan(css.indexOf(".mk-card { color: red; }"));
		expect(doc.body.querySelector(".fac-page-root > .mk-card").textContent).toBe("Plan");
		expect(doc.querySelectorAll("link, script")).toHaveLength(0);
	});

	it("keeps a style that closes its own tag inside the style element", () => {
		const doc = parse(fac_page_draft_srcdoc({ html: "", style: "</style><form action='x'></form>", kit_css: "" }));
		expect(doc.querySelector("form")).toBeNull();
		expect(doc.head.querySelectorAll("style")).toHaveLength(1);
	});

	it("survives missing html, style and kit", () => {
		expect(parse(fac_page_draft_srcdoc({})).head.firstElementChild.getAttribute("content")).toBe(CSP);
	});
});

describe("fac_page_draft_frame", () => {
	it("is an iframe with an empty sandbox and the srcdoc", () => {
		const frame = fac_page_draft_frame({ html: "<p>x</p>", style: "", kit_css: "" });
		expect(frame.tagName).toBe("IFRAME");
		expect(frame.getAttribute("sandbox")).toBe("");
		expect(frame.srcdoc).toContain("<p>x</p>");
		expect(frame.srcdoc).toContain(CSP);
	});
});
