import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import { findFrappeJs, loadDeskFormatter } from "./__tests__/deskFormatter";
import { FORMAT_CASES } from "./__tests__/pageFormatCases";
import { formatValue } from "./pageFormat";

// What Desk's frappe.format returned for each case, by title. Generated from Frappe's own scripts
// in a bench (deskFormatter.js) by running, in chat/frontend:
//   FAC_WRITE_FORMAT_FIXTURE=1 npx vitest run src/utils/pageFormat.parity.spec.js
// Recorded from Frappe 16.52.0. CI has no Frappe checkout beside this app, so it checks the
// recording; in a bench the live block below checks Frappe's code itself.
const FIXTURE = resolve(import.meta.dirname, "__tests__/pageFormatCases.desk.json");
const FRAPPE_JS = findFrappeJs();

const format = (c) => formatValue(c.settings, c.value, c.df, c.options, c.doc);

// What a Shared page in Desk gets from frappe.format: Desk's output through fac_page_frappe.js.
const WRAPPER = readFileSync(resolve(import.meta.dirname, "../../../../assistant_core/page/fac_pages/fac_page_frappe.js"), "utf-8");
const fac_page_frappe = new Function(`${WRAPPER}\nreturn fac_page_frappe;`)();
const onDeskPage = (html, c) => fac_page_frappe({ format: () => html }).format(c.value, c.df, c.options, c.doc);

describe("frappe.format outside Desk, against Frappe's recorded output", () => {
	const recorded = existsSync(FIXTURE) ? JSON.parse(readFileSync(FIXTURE, "utf-8")) : {};

	it("has a recording for every case", () => {
		expect(Object.keys(recorded).sort()).toEqual(FORMAT_CASES.map((c) => c.title).sort());
	});

	it.each(FORMAT_CASES.map((c) => [c.title, c]))("%s", (title, c) => {
		expect(format(c)).toBe(onDeskPage(recorded[title], c));
	});
});

describe.skipIf(!FRAPPE_JS)("frappe.format outside Desk, against Frappe's code in this bench", () => {
	let desk;
	beforeAll(() => {
		desk = loadDeskFormatter(FRAPPE_JS);
		if (process.env.FAC_WRITE_FORMAT_FIXTURE) {
			const recording = Object.fromEntries(FORMAT_CASES.map((c) => [c.title, desk(c.settings, c.value, c.df, c.options, c.doc)]));
			writeFileSync(FIXTURE, `${JSON.stringify(recording, null, "\t")}\n`);
		}
	});

	it("shows Desk's html, which is why a page needs its text", () => {
		const c = FORMAT_CASES.find((x) => x.title === "Currency 79360 in #,##,###.##");
		expect(desk(c.settings, c.value, c.df)).toBe("<div style='text-align: right'>₹ 79,360.00</div>");
	});

	it.each(FORMAT_CASES.map((c) => [c.title, c]))("%s", (title, c) => {
		const html = desk(c.settings, c.value, c.df, c.options, c.doc);
		expect(format(c)).toBe(onDeskPage(html, c));
	});
});
