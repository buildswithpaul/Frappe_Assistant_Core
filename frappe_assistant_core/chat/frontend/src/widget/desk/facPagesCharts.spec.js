import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { facPagesSource } from "./facPagesSource";

// The fac-pages Desk page script, run as Desk runs it: a plain script with frappe and __ global.
const SOURCE = facPagesSource();
const CHARTS_SRC = "/assets/frappe_assistant_core/js/fac_page_charts.js?v=build-7";

let frappe;
let wrapper;

// A shared published page, whose script runs at once; facPagesGate.spec.js covers held ones.
const published = {
	title: "Sales",
	html: '<div class="chart"></div>',
	style: "",
	draft: false,
	visibility: "Shared",
	script: "fac.chart(root_element.querySelector('.chart'), {series: [{type: 'bar', data: [1]}]});",
};

function loadDeskPage(initial = published) {
	let page = initial;
	const main = { empty: () => main, append: (el) => main.el.append(el), el: document.createElement("div") };
	frappe = {
		pages: { "fac-pages": {} },
		ui: { make_app_page: () => ({ main, set_title: vi.fn() }) },
		get_route: () => ["fac-pages", "sales"],
		call: ({ callback }) => callback({ message: page }),
		setPage: (next) => (page = next),
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

// What create_shadow_element does with the js it is given: a global script (frappe is a Desk
// global) whose only own binding is root_element, the shadow root.
function runAsDesk(js, root) {
	new Function("ROOT", "frappe", `(function () { let root_element = ROOT; ${js} })();`)(root, frappe);
}

// Show the page and run the script create_shadow_element was given, as the browser would.
async function showAndRun() {
	const before = frappe.create_shadow_element.mock.calls.length;
	show();
	// A repeated load event is harmless: the bundle promise has already settled.
	if (chartScripts().length) finishLoading();
	await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledTimes(before + 1));
	const root = document.createElement("div");
	root.innerHTML = '<div class="chart"></div>';
	runAsDesk(frappe.create_shadow_element.mock.calls.at(-1)[3], root);
	return root;
}

beforeEach(() => {
	window._version_number = "build-7";
	window.fac_page_charts = { chart: vi.fn(() => ({ dispose: vi.fn() })) };
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

	it("does not load the bundle for a script that never names fac", async () => {
		loadDeskPage({ ...published, script: "root_element.querySelector('.chart').textContent = 'no chart';" });
		show();
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledOnce());
		expect(chartScripts()).toHaveLength(0);
	});

	it("disposes the charts the shown page drew before it renders the next one", async () => {
		loadDeskPage();
		await showAndRun();
		const handle = window.fac_page_charts.chart.mock.results[0].value;
		expect(handle.dispose).not.toHaveBeenCalled();
		await showAndRun();
		expect(handle.dispose).toHaveBeenCalledOnce();
	});

	it("disposes a chart a page draws after the user moved on", async () => {
		loadDeskPage();
		show();
		finishLoading();
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledOnce());
		// The script reads fac when it starts and may draw later, after its data arrives.
		const late = { ...published, script: "window.__drawLater = () => fac.chart(root_element, {});" };
		frappe.setPage(late);
		show();
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledTimes(2));
		runAsDesk(frappe.create_shadow_element.mock.calls[1][3], document.createElement("div"));
		frappe.setPage({ ...published, script: "" });
		show();
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledTimes(3));
		const handle = window.__drawLater();
		expect(handle.dispose).toHaveBeenCalledOnce();
		delete window.__drawLater;
	});

	it("tells a page script that charts could not be loaded when the bundle failed", async () => {
		delete window.fac_page_charts;
		loadDeskPage();
		show();
		finishLoading("error");
		await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledOnce());
		const js = frappe.create_shadow_element.mock.calls[0][3];
		const root = document.createElement("div");
		root.innerHTML = '<div class="chart"></div>';
		expect(() => runAsDesk(js, root)).toThrow("Charts could not be loaded");
	});
});
