// @vitest-environment node
// Builds the Desk chart bundle with its real config and loads it the way Desk does: a classic
// script in a browser window, which has no Node `process`.
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { JSDOM } from "jsdom";
import { build } from "vite";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

const ROOT = resolve(import.meta.dirname, "../..");
let outDir;
let bundle;

beforeAll(async () => {
	outDir = mkdtempSync(join(tmpdir(), "fac-page-charts-"));
	await build({
		configFile: resolve(ROOT, "vite.pagecharts.config.js"),
		root: ROOT,
		logLevel: "silent",
		build: { outDir, emptyOutDir: true },
	});
	bundle = readFileSync(join(outDir, "fac_page_charts.js"), "utf-8");
}, 60000);

afterAll(() => outDir && rmSync(outDir, { recursive: true, force: true }));

function browserWindow() {
	const dom = new JSDOM('<!doctype html><div id="c"></div>', { runScripts: "outside-only" });
	// ECharts measures label text on a 2D canvas, which every browser has and jsdom lacks.
	dom.window.HTMLCanvasElement.prototype.getContext = () => ({
		font: "",
		measureText: (text) => ({ width: String(text).length * 7 }),
	});
	return dom.window;
}

describe("the Desk chart bundle", () => {
	it("leaves no Node process lookup in the browser script", () => {
		expect(/\bprocess\.env\b/.test(bundle)).toBe(false);
	});

	it("loads in a window without process and draws an svg chart", () => {
		const win = browserWindow();
		expect(win.eval("typeof process")).toBe("undefined");
		win.eval(bundle);
		win.eval(
			"fac_page_charts.chart(document.getElementById('c'), {xAxis: {type: 'category', data: ['A']}, yAxis: {}, series: [{type: 'bar', data: [3]}]});",
		);
		expect(win.document.querySelector("#c svg")).not.toBeNull();
	});
});
