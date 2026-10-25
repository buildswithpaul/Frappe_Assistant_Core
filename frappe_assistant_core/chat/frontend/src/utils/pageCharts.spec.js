import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { QL_VIZ_SEQUENCE } from "@/composables/dataVizPalette";

import { chart } from "./pageCharts";

const option = {
	xAxis: { type: "category", data: ["Jan", "Feb", "Mar"] },
	yAxis: { type: "value" },
	series: [{ type: "bar", data: [120, 200, 150] }],
};

// ECharts measures label text on a 2D canvas, which every browser has and jsdom lacks.
beforeAll(() => {
	vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
		font: "",
		measureText: (text) => ({ width: String(text).length * 7 }),
	});
});
afterAll(() => vi.restoreAllMocks());

let el;
let handle;

function mountChart(opts = option) {
	el = document.createElement("div");
	document.body.append(el);
	handle = chart(el, opts);
	return handle;
}

afterEach(() => {
	handle?.dispose();
	el?.remove();
	handle = el = null;
});

describe("chart", () => {
	it("draws the chart as svg inside the element", () => {
		mountChart();
		expect(el.querySelector("svg")).not.toBeNull();
		expect(el.querySelector("canvas")).toBeNull();
	});

	it("marks the element as a chart container, so the kit can size it and keep it whole in print", () => {
		mountChart();
		expect(el.classList.contains("mk-chart")).toBe(true);
	});

	it("colours series with the data-viz palette", () => {
		mountChart();
		const fills = [...el.querySelectorAll("path")].map((p) => p.getAttribute("fill"));
		expect(fills.map((f) => f?.toUpperCase())).toContain(QL_VIZ_SEQUENCE[0].toUpperCase());
	});

	it("keeps a palette the page sets itself", () => {
		mountChart({ ...option, color: ["#123456"] });
		const fills = [...el.querySelectorAll("path")].map((p) => p.getAttribute("fill"));
		expect(fills).toContain("#123456");
	});

	it("updates the chart in place", () => {
		mountChart();
		handle.update({ series: [{ type: "bar", data: [1, 2, 3] }], color: ["#abcdef"] });
		const fills = [...el.querySelectorAll("path")].map((p) => p.getAttribute("fill"));
		expect(fills).toContain("#abcdef");
	});

	it("empties the element when disposed", () => {
		mountChart();
		handle.dispose();
		expect(el.querySelector("svg")).toBeNull();
	});

	it("names the series types it draws when a page asks for another", () => {
		expect(() => mountChart({ series: [{ type: "scatter", data: [[1, 2]] }] })).toThrow(
			'fac.chart draws bar, line and pie series, not "scatter"',
		);
		mountChart();
		expect(() => handle.update({ series: { type: "radar", data: [] } })).toThrow('not "radar"');
	});

	it("draws a pie and a line chart", () => {
		mountChart({ series: [{ type: "pie", data: [{ name: "A", value: 1 }, { name: "B", value: 2 }] }] });
		expect(el.querySelectorAll("path").length).toBeGreaterThan(1);
		handle.dispose();
		el.remove();
		mountChart({ ...option, series: [{ type: "line", data: [1, 3, 2] }] });
		expect(el.querySelector("svg")).not.toBeNull();
	});
});
