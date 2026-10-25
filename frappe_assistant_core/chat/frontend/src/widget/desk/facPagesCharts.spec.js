import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The fac-pages Desk page script, run as Desk runs it: a plain script with frappe and __ global.
const SOURCE = readFileSync(
	resolve(import.meta.dirname, "../../../../../assistant_core/page/fac_pages/fac_pages.js"),
	"utf-8",
);
const CHARTS_SRC = "/assets/frappe_assistant_core/js/fac_page_charts.js?v=build-7";

let frappe;
let wrapper;

const published = {
	title: "Sales",
	html: '<div class="chart"></div>',
	style: "",
	draft: false,
	script: "fac.chart(root_element.querySelector('.chart'), {series: [{type: 'bar', data: [1]}]});",
};

function loadDeskPage(page = published) {
	const main = { empty: () => main, append: (el) => main.el.append(el), el: document.createElement("div") };
	frappe = {
		pages: { "fac-pages": {} },
		ui: { make_app_page: () => ({ main, set_title: vi.fn() }) },
		get_route: () => ["fac-pages", "sales"],
		call: ({ callback }) => callback({ message: page }),
		create_shadow_element: vi.fn(),
	};
	new Function("frappe", "__", "$", SOURCE)(frappe, (s) => s, vi.fn());
	wrapper = {};
	frappe.pages["fac-pages"].on_page_load(wrapper);
}

const show = () => frappe.pages["fac-pages"].on_page_show(wrapper);
const chartScripts = () => [...document.head.querySelectorAll("script")].filter((s) => s.src.includes("fac_page_charts"));
// jsdom fetches no script; the browser fires load or error once the bundle has run or failed.
const finishLoading = (type = "load") => chartScripts().at(-1).dispatchEvent(new Event(type));

// What create_shadow_element does with the js it is given: a global script whose only binding is
// root_element, the shadow root.
function runAsDesk(js, root) {
	new Function("ROOT", `(function () { let root_element = ROOT; ${js} })();`)(root);
}

beforeEach(() => {
	window._version_number = "build-7";
	window.fac_page_charts = { chart: vi.fn() };
});

afterEach(() => {
	chartScripts().forEach((s) => s.remove());
	delete window.fac_page_charts;
	delete window._version_number;
});

describe("fac-pages Desk page and fac.chart", () => {
	it("loads the chart bundle, versioned, before it renders the page", async () => {
		loadDeskPage();
		show();
		expect(chartScripts().map((s) => s.getAttribute("src"))).toEqual([CHARTS_SRC]);
		expect(frappe.create_shadow_element).not.toHaveBeenCalled();
		finishLoading();
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledOnce());
	});

	it("loads the bundle once for every page shown", async () => {
		loadDeskPage();
		show();
		finishLoading();
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledOnce());
		show();
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledTimes(2));
		expect(chartScripts()).toHaveLength(1);
	});

	it("runs the page script with fac.chart from the bundle, as the chat panel does", async () => {
		loadDeskPage();
		show();
		finishLoading();
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledOnce());
		const js = frappe.create_shadow_element.mock.calls[0][3];
		const root = document.createElement("div");
		root.innerHTML = '<div class="chart"></div>';
		runAsDesk(js, root);
		expect(window.fac_page_charts.chart).toHaveBeenCalledWith(root.querySelector(".chart"), {
			series: [{ type: "bar", data: [1] }],
		});
	});

	it("still renders the page when the bundle fails to load, and tries again on the next show", async () => {
		loadDeskPage();
		show();
		finishLoading("error");
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledOnce());
		show();
		expect(chartScripts()).toHaveLength(2);
	});
});
