/**
 * `fac.chart(el, option)`: the one way a FAC Page script draws a chart, in the chat panel and in
 * Desk alike. The Desk copy is this module built on its own (vite.pagecharts.config.js), so it
 * registers only the charts and components pages use, and draws SVG so a printed page stays sharp.
 */
import { BarChart, LineChart, PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, TitleComponent, TooltipComponent } from "echarts/components";
import { init, use } from "echarts/core";
import { SVGRenderer } from "echarts/renderers";

import { QL_VIZ_SEQUENCE } from "@/composables/dataVizPalette";

use([
	BarChart,
	LineChart,
	PieChart,
	GridComponent,
	TooltipComponent,
	LegendComponent,
	TitleComponent,
	SVGRenderer,
]);

// The kit sizes and print-protects this class.
const CHART_CLASS = "mk-chart";
// Room for the axis labels inside the chart's box: ECharts' default margins cut long values off.
const DEFAULT_GRID = { left: 8, right: 16, top: 24, bottom: 8, containLabel: true };
// The series types registered above; ECharts would skip any other silently.
const SERIES_TYPES = ["bar", "line", "pie"];

// A page's theme is on its shadow host, or on a frame's own document. A dark chart uses ECharts'
// dark theme for its text and lines, over the page's own background, and redraws when it changes.
function themeHolder(el) {
	const root = el.getRootNode();
	return root instanceof ShadowRoot ? root.host : el.ownerDocument.documentElement;
}

// What a chart would size to before it is laid out, as in a test or a hidden panel.
const FALLBACK_SIZE = { width: 600, height: 320 };

function checkSeries(option) {
	const series = [].concat(option?.series || []);
	const other = series.find((s) => s && s.type && !SERIES_TYPES.includes(s.type));
	if (other) throw new Error(`fac.chart draws bar, line and pie series, not "${other.type}"`);
}

/**
 * Draw `option` (an ECharts option) into `el`.
 *
 * @param {HTMLElement} el the container; the kit gives it a default height
 * @param {object} option an ECharts option; `color` defaults to the data-viz palette
 * @returns {{update: (option: object) => void, dispose: () => void}} `update` merges a new option
 *   in, as ECharts' setOption does; `dispose` removes the chart and empties `el`.
 * @throws {Error} for a series type other than bar, line or pie.
 */
export function chart(el, option = {}) {
	checkSeries(option);
	el.classList.add(CHART_CLASS);
	const base = { color: QL_VIZ_SEQUENCE, grid: DEFAULT_GRID, ...option };
	// Replayed after a redraw for a new theme, so the chart keeps what the page set since.
	const updates = [];
	const holder = themeHolder(el);
	let instance = null;
	let theme = null;

	// A print is light, so a dark chart hands snapshotHtml a light copy of itself (pagePrint.js).
	function lightSvg() {
		const size = { width: instance.getWidth() || FALLBACK_SIZE.width, height: instance.getHeight() || FALLBACK_SIZE.height };
		const copy = init(null, null, { renderer: "svg", ssr: true, ...size });
		copy.setOption({ ...base, animation: false });
		updates.forEach((next) => copy.setOption(next));
		const svg = copy.renderToSVGString();
		copy.dispose();
		return svg;
	}

	function draw() {
		const next = holder.getAttribute("data-theme") === "dark" ? "dark" : "light";
		if (next === theme) return;
		theme = next;
		instance?.dispose();
		instance = init(el, theme === "dark" ? "dark" : null, { renderer: "svg" });
		instance.setOption(theme === "dark" ? { backgroundColor: "transparent", ...base } : base);
		updates.forEach((update) => instance.setOption(update));
		if (theme === "dark") el.facLightSvg = lightSvg;
		else delete el.facLightSvg;
	}

	draw();
	const themeObserver = new MutationObserver(draw);
	themeObserver.observe(holder, { attributes: true, attributeFilter: ["data-theme"] });
	// The panel and Desk both resize with the window and the chat beside them.
	const observer = typeof ResizeObserver === "function" ? new ResizeObserver(() => instance.resize()) : null;
	observer?.observe(el);

	return {
		update(next) {
			checkSeries(next);
			updates.push(next);
			instance.setOption(next);
		},
		dispose() {
			themeObserver.disconnect();
			observer?.disconnect();
			instance.dispose();
			delete el.facLightSvg;
		},
	};
}
