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

// The kit sizes and print-protects this class; pages render on the kit's light surface.
const CHART_CLASS = "mk-chart";
// The series types registered above; ECharts would skip any other silently.
const SERIES_TYPES = ["bar", "line", "pie"];

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
	const instance = init(el, null, { renderer: "svg" });
	instance.setOption({ color: QL_VIZ_SEQUENCE, ...option });

	// The panel and Desk both resize with the window and the chat beside them.
	const observer = typeof ResizeObserver === "function" ? new ResizeObserver(() => instance.resize()) : null;
	observer?.observe(el);

	return {
		update(next) {
			checkSeries(next);
			instance.setOption(next);
		},
		dispose() {
			observer?.disconnect();
			instance.dispose();
		},
	};
}
