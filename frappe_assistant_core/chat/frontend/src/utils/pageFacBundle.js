/**
 * What the fac-pages Desk page and a personal page's frame load as one classic script,
 * window.fac_page_charts (vite.pagecharts.config.js): fac.chart, fac.report and the page tools, so every host
 * runs the same code as the chat panel. The global keeps its first name so no host's loader
 * changes.
 */
export { deskBlocks, makeBlocks } from "./pageBlocks";
export { chart } from "./pageCharts";
export { report } from "./pageReport";
