import { describe, expect, it } from "vitest";

// One set of cases for both copies of the draft builder: this ES module for the chat SPA, and the
// plain script the fac-pages Desk page inlines through render_include, which cannot load a module.
const CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:";

function parse(srcdoc) {
	return new DOMParser().parseFromString(srcdoc, "text/html");
}

export function describeDraftBuilder(label, { srcdoc: buildSrcdoc, frame: buildFrame, shownTheme }) {
	describe(`${label}: draft srcdoc`, () => {
		const srcdoc = buildSrcdoc({
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

		it("draws the draft in Desk's theme, and anything but dark is light", () => {
			const themed = (theme) => parse(buildSrcdoc({ html: "", style: "", kit_css: "", theme })).documentElement.getAttribute("data-theme");
			expect(themed("dark")).toBe("dark");
			expect([themed(undefined), themed("light"), themed('"><b>')]).toEqual(["light", "light", "light"]);
		});

		it("keeps a style that closes its own tag inside the style element", () => {
			const doc = parse(buildSrcdoc({ html: "", style: "</style><form action='x'></form>", kit_css: "" }));
			expect(doc.querySelector("form")).toBeNull();
			expect(doc.head.querySelectorAll("style")).toHaveLength(1);
		});

		it("survives missing html, style and kit", () => {
			expect(parse(buildSrcdoc({})).head.firstElementChild.getAttribute("content")).toBe(CSP);
		});
	});

	describe(`${label}: draft frame`, () => {
		it("is an iframe with an empty sandbox and the srcdoc", () => {
			const frame = buildFrame({ html: "<p>x</p>", style: "", kit_css: "" });
			expect(frame.tagName).toBe("IFRAME");
			expect(frame.getAttribute("sandbox")).toBe("");
			expect(frame.srcdoc).toContain("<p>x</p>");
			expect(frame.srcdoc).toContain(CSP);
		});
	});

	describe(`${label}: the theme a page is shown in`, () => {
		it("follows a dark Desk when the page colours only with the kit's tokens", () => {
			const page = { html: '<div class="mk-card" style="padding: 8px">Sales</div>', style: ".x { background: var(--mk-surface); }" };
			expect(shownTheme(page, "dark")).toBe("dark");
			expect(shownTheme(page, "light")).toBe("light");
		});

		it.each([
			["a hex colour in its style", { style: ".card { background: #fff; }" }],
			["an rgb colour in its style", { style: ".card { color: rgb(17, 17, 17); }" }],
			["an hsl colour in its style", { style: ".card { color: hsl(0 0% 10%); }" }],
			["a named colour in its style", { style: ".card { background: white; }" }],
			["a colour in an inline style", { html: '<div style="color:#b42318">-4,200</div>' }],
		])("stays light when the page sets its own colours: %s", (_, page) => {
			expect(shownTheme(page, "dark")).toBe("light");
		});

		it("is not misled by words in the page's text", () => {
			expect(shownTheme({ html: "<p>Black Friday orders, white goods</p>", style: "" }, "dark")).toBe("dark");
		});

		it("is light for anything but a dark Desk", () => {
			expect(shownTheme({}, "automatic")).toBe("light");
			expect(shownTheme({}, undefined)).toBe("light");
		});
	});
}
