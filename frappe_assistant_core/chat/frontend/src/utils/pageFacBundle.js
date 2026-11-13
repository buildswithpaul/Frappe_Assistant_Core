/**
 * What the fac-pages Desk page and a personal page's frame load as one classic script,
 * window.fac_page_charts (vite.pagecharts.config.js): fac.chart and fac.report, so every host
 * runs the same code as the chat panel. The global keeps its first name so no host's loader
 * changes.
 */
export { chart } from "./pageCharts";
export { report } from "./pageReport";
