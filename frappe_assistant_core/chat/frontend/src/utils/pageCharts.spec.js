import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { getInstanceByDom } from "echarts/core";

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

	it("keeps axis labels inside the chart, unless the page lays out the grid itself", () => {
		// Six-figure totals ran past ECharts' default left margin and lost their leading digits.
		mountChart();
		expect(getInstanceByDom(el).getOption().grid[0].containLabel).toBe(true);
		handle.dispose();
		el.remove();
		mountChart({ ...option, grid: { left: 40, containLabel: false } });
		expect(getInstanceByDom(el).getOption().grid[0]).toMatchObject({ left: 40, containLabel: false });
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

	describe("in a dark page", () => {
		// What the axis labels are drawn in, read off the svg ECharts drew.
		const labelFills = (root) => [...root.querySelectorAll("svg text")].map((t) => t.getAttribute("fill") || t.style.fill);

		it("draws readable text on a page whose shadow host is dark, on the page's own background", () => {
			const host = document.createElement("div");
			host.setAttribute("data-theme", "dark");
			document.body.append(host);
			const shadow = host.attachShadow({ mode: "open" });
			el = document.createElement("div");
			shadow.append(el);
			handle = chart(el, option);
			const opt = getInstanceByDom(el).getOption();
			expect(opt.backgroundColor).toBe("transparent");
			const light = (fill) => /^#(e|f|d|c|b|a|9)/i.test(fill) || /^rgba?\((1[5-9]\d|2\d\d)/.test(fill);
			expect(labelFills(el).filter(Boolean).every(light)).toBe(true);
			host.remove();
		});

		it("draws a frame's chart dark when the frame's document is dark", () => {
			document.documentElement.setAttribute("data-theme", "dark");
			mountChart();
			expect(getInstanceByDom(el).getOption().backgroundColor).toBe("transparent");
			document.documentElement.removeAttribute("data-theme");
		});

		// ECharts' dark theme draws axis labels in this colour.
		const DARK_LABEL = /#b9b8ce/i;
		const darkHost = () => {
			const host = document.createElement("div");
			host.setAttribute("data-theme", "dark");
			document.body.append(host);
			const shadow = host.attachShadow({ mode: "open" });
			el = document.createElement("div");
			shadow.append(el);
			return { host, shadow };
		};

		it("redraws when the page's theme changes", async () => {
			const { host } = darkHost();
			handle = chart(el, option);
			handle.update({ title: { text: "Sales" } });
			host.setAttribute("data-theme", "light");
			await new Promise((resolve) => setTimeout(resolve, 0));
			const opt = getInstanceByDom(el).getOption();
			expect(opt.backgroundColor).not.toBe("transparent");
			expect(opt.title[0].text).toBe("Sales");
			expect(el.innerHTML).not.toMatch(DARK_LABEL);
			host.remove();
		});

		it("prints a dark page's chart in light colours, on paper", async () => {
			const { host, shadow } = darkHost();
			const root = document.createElement("div");
			root.className = "fac-page-root";
			shadow.append(root);
			root.append(el);
			handle = chart(el, option);
			expect(el.innerHTML).toMatch(DARK_LABEL);
			const { snapshotHtml } = await import("./pagePrint");
			const printed = snapshotHtml(root);
			expect(printed).toContain("<svg");
			expect(printed).toContain("Feb");
			expect(printed).not.toMatch(DARK_LABEL);
			host.remove();
		});

		it("keeps a light page's chart as it was", () => {
			mountChart();
			expect(getInstanceByDom(el).getOption().backgroundColor).not.toBe("transparent");
		});
	});
});
